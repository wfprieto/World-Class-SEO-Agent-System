"""Hermetic regressions for fresh-scan parser, network and allocation bounds."""

from __future__ import annotations

import subprocess
import sys
import socket
import threading
import time
import urllib.error

import pytest


def _bounded_python(code: str) -> None:
    try:
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True,
                                text=True, timeout=2, check=False)
    except subprocess.TimeoutExpired:
        raise AssertionError('analysis exceeded the controlled work bound') from None
    assert result.returncode == 0, result.stderr


def test_spa_unterminated_script_is_bounded() -> None:
    code = (
        "from adapters.rendered_page import is_spa; "
        "assert is_spa('<div id=\"root\"></div><script>' + '<script>' * 50000); "
        "assert not is_spa('<div id=\"root\">' + 'word ' * 121 + '</div>')"
    )
    try:
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True,
                                text=True, timeout=2, check=False)
    except subprocess.TimeoutExpired:
        raise AssertionError('SPA detection exceeded the controlled work bound') from None
    assert result.returncode == 0, result.stderr


def test_llm_private_endpoint_denied_before_dial(monkeypatch) -> None:
    from runtime.llm import OpenAICompatibleClient

    def forbid_socket(*_args, **_kwargs):
        raise AssertionError('private endpoint reached socket creation')

    monkeypatch.setattr('socket.socket', forbid_socket)
    client = OpenAICompatibleClient(api_key='fixture-key',
                                   base_url='https://127.0.0.1/v1',
                                   allow_custom_base_url=True)
    with pytest.raises(ValueError, match='non-public'):
        client._post_json_with_retry('https://127.0.0.1/v1/chat/completions', {})


def test_accessibility_malformed_images_are_bounded() -> None:
    _bounded_python(
        "from adapters.accessibility_checker import AccessibilityCheckerAdapter as A; "
        "import pytest; "
        "\nwith pytest.raises(ValueError,match='ceiling'): A().fetch(html='<img ' * 50000)\n"
        "r=A().fetch(html='<H1>Title</H1><IMG ALT = \"\" src=x><img src=y>'); "
        "assert r.data == {'image_count':2,'missing_alt_count':1,'h1_count':1}"
    )


def test_content_heading_whitespace_is_bounded() -> None:
    _bounded_python(
        "from integrations.content_intelligence.analysis import quality_measurements,compare_texts; "
        "text='# x'+' '*100000+'y'; "
        "assert quality_measurements(text)['metrics']['heading_count']==1; "
        "assert compare_texts(text,'### Other','a','b')['right']['headings']==['Other']"
    )


@pytest.mark.parametrize('phase', ['headers', 'body', 'error'])
def test_http_total_deadline_closes_active_socket(monkeypatch, phase) -> None:
    from integrations.technical.http import BoundedHttpClient

    client_socket, server_socket = socket.socketpair()
    stopped = threading.Event()

    def server() -> None:
        try:
            server_socket.recv(10000)
            if phase != 'headers':
                status = b'404 Missing' if phase == 'error' else b'200 OK'
                server_socket.sendall(b'HTTP/1.1 ' + status + b'\r\nContent-Length: 30\r\n\r\n')
            payload = (b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok'
                       if phase == 'headers' else b'x' * 30)
            for byte in payload:
                server_socket.sendall(bytes([byte]))
                time.sleep(.015)
        except OSError:
            pass
        finally:
            server_socket.close()
            stopped.set()

    def connection(*_args, timeout=30, **_kwargs):
        client_socket.settimeout(timeout)
        return client_socket

    monkeypatch.setattr('security.pinned_http.public_connection', connection)
    worker = threading.Thread(target=server)
    worker.start()
    started = time.monotonic()
    try:
        with pytest.raises((TimeoutError, OSError), match='deadline|timed out|closed'):
            BoundedHttpClient(timeout=.08).get('http://93.184.216.34/')
        assert time.monotonic() - started < .3
    finally:
        client_socket.close()
        server_socket.close()
        worker.join(1)
    assert stopped.is_set()


def test_rdap_private_endpoint_denied_before_dial(monkeypatch) -> None:
    from integrations.authority_media.transport import BoundedTransport

    def forbid_socket(*_args, **_kwargs):
        raise AssertionError('RDAP private endpoint reached socket creation')

    monkeypatch.setattr('socket.socket', forbid_socket)
    with pytest.raises(ValueError, match='non-public'):
        BoundedTransport({'127.0.0.1'}, max_attempts=1).get('https://127.0.0.1/domain/example')


@pytest.mark.parametrize('metric,periods', [
    ({'percentilesTimeseries': {'p75s': [1] * 41}}, []),
    ({'histogramTimeseries': [{}] * 51}, [{}]),
    ({'histogramTimeseries': [{'densities': [0] * 41}]}, [{}]),
    ({}, [{}] * 41),
])
def test_crux_dimensions_rejected_before_expansion(metric, periods) -> None:
    from integrations.google.crux import CrUXHistoryAdapter

    with pytest.raises(ValueError, match='CrUX.*dimension'):
        CrUXHistoryAdapter._normalize_metric_series(metric, periods)
    assert CrUXHistoryAdapter._normalize_metric_series(
        {'percentilesTimeseries': {'p75s': [10, None]}}, [{}]
    ) == [{'collection_period': {}, 'p75': 10., 'histogram': []},
          {'collection_period': None, 'p75': None, 'histogram': []}]


def test_link_expansion_is_bounded_before_normalization() -> None:
    from integrations.product_proof.link_extractor import extract_link_evidence

    called = []
    def normalized(value):
        called.append(value)
        return value

    with pytest.raises(ValueError, match='URL evidence.*ceiling'):
        extract_link_evidence([{'href': 'a'}], 'https://example.com/' + 'x' * 10000,
                              'example.com', normalized)
    assert called == []
    links = extract_link_evidence([{'href': '/next', 'rel': 'next'},
                                   {'href': '/preferred', 'rel': 'canonical'}],
                                  'https://example.com/page', 'example.com', normalized)
    assert links.rel_next == {'https://example.com/next'}
    assert links.canonical == 'https://example.com/preferred'


def test_sitemap_dns_work_is_cached_and_capped(monkeypatch) -> None:
    from integrations.technical.http import HttpHop
    from integrations.technical.inspection import TechnicalInspectionService

    calls = []
    def resolver(host, port, **_kwargs):
        calls.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', port))]

    locations = [f'https://same.example/{i}' for i in range(100)]
    locations += [f'https://host{i}.example/' for i in range(100)]
    body = ('<urlset>' + ''.join(f'<url><loc>{url}</loc></url>' for url in locations)
            + '</urlset>').encode()
    class HTTP:
        def get(self, url):
            return HttpHop(url, url, 200, {}, body, 1)

    monkeypatch.setattr(socket, 'getaddrinfo', resolver)
    result = TechnicalInspectionService(http=HTTP()).sitemap('https://93.184.216.34/sitemap')
    assert calls.count('same.example') == 1
    assert len(calls) <= 64
    assert result.data['data_state'] == 'PARTIAL'
    assert result.data['unclassified_count'] > 0


@pytest.mark.parametrize('status', [200, 404, 429])
def test_authority_total_deadline_and_error_cleanup(status) -> None:
    from integrations.authority_media.transport import BoundedTransport

    class Response:
        headers = {}
        closed = False
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            self.close()
        def getcode(self):
            return status
        def geturl(self):
            return 'https://93.184.216.34/'
        def read(self, _limit):
            time.sleep(.06)
            return b'body'
        def close(self):
            self.closed = True

    response = Response()
    class Opener:
        def open(self, request, *, timeout):
            if status != 200:
                if status == 429:
                    time.sleep(.06)
                raise urllib.error.HTTPError(request.full_url, status, 'synthetic', {}, response)
            return response

    transport = BoundedTransport({'93.184.216.34'}, timeout_seconds=.03,
                                 opener=Opener(), sleeper=lambda _delay: None)
    with pytest.raises(TimeoutError, match='deadline'):
        transport.get('https://93.184.216.34/', accepted_statuses={200, 404})
    assert response.closed
    assert transport.request_count == 1


def test_spa_large_script_comparison_is_preserved() -> None:
    from adapters.rendered_page import is_spa

    script = '<script>const value="' + '<' + 'x' * 100000 + '";</script>'
    assert not is_spa('<div id="root">' + 'word ' * 121 + '</div>' + script)


def test_failed_tls_handshake_closes_wrapped_socket(monkeypatch) -> None:
    from security.pinned_http import PinnedHTTPSConnection

    class Socket:
        closed = False
        def close(self):
            self.closed = True
        def settimeout(self, _timeout):
            pass
        def do_handshake(self):
            raise OSError('synthetic TLS failure')

    raw, wrapped = Socket(), Socket()
    monkeypatch.setattr('security.pinned_http.public_connection', lambda *_a, **_k: raw)
    monkeypatch.setattr('ssl.SSLContext.wrap_socket', lambda *_a, **_k: wrapped)
    with pytest.raises(OSError, match='synthetic TLS failure'):
        PinnedHTTPSConnection('public.example').connect()
    assert raw.closed and wrapped.closed


@pytest.mark.parametrize('timeout', [float('nan'), float('inf'), float('-inf')])
def test_nonfinite_request_timeouts_are_rejected(timeout) -> None:
    from integrations.authority_media.transport import BoundedTransport
    from integrations.technical.http import BoundedHttpClient

    with pytest.raises(ValueError):
        BoundedHttpClient(timeout=timeout)
    with pytest.raises(ValueError):
        BoundedTransport({'93.184.216.34'}, timeout_seconds=timeout)


def test_url_evidence_aggregate_stops_before_next_expansion() -> None:
    from integrations.product_proof.link_extractor import extract_link_evidence

    calls = []
    links = [{'href': str(index)} for index in range(500)]
    with pytest.raises(ValueError, match='aggregate character ceiling'):
        extract_link_evidence(links, 'https://example.com/' + 'x' * 4000,
                              'example.com', lambda value: calls.append(value) or value)
    assert 1 < len(calls) < len(links)


@pytest.mark.parametrize('field', ['asset', 'image'])
def test_media_url_bounds_cover_assets_and_images(field) -> None:
    from integrations.product_proof.url_evidence_bounds import URLBudget, extract_media_evidence

    assets = ['x' * 9000] if field == 'asset' else []
    images = [{'src': 'x' * 9000}] if field == 'image' else []
    with pytest.raises(ValueError, match='per-URL character ceiling'):
        extract_media_evidence(assets, images, 'https://example.com/', lambda url: url, URLBudget())


def test_crawl_url_budget_is_shared_across_pages(monkeypatch) -> None:
    from integrations.product_proof.crawler import SiteCrawler
    from integrations.product_proof.models import CrawlConfig
    from integrations.technical.http import HttpHop

    class HTTP:
        def get(self, url):
            if url.endswith('robots.txt'):
                body = b'User-agent: *\nAllow: /'
            else:
                index = int(url.rsplit('/', 1)[-1] or '0') + 1
                body = f'<h1>Page</h1><a href="/{index}">Next</a>'.encode()
            return HttpHop(url, url, 200, {}, body, 1)

    monkeypatch.setattr('integrations.product_proof.url_evidence_bounds.CRAWL_URL_CHARS', 400)
    result = SiteCrawler(config=CrawlConfig(max_urls=10, max_depth=10), http=HTTP(),
                         url_validator=lambda url: url).crawl('https://example.com/')
    assert result['pages']
    assert result['data_state'] == 'PARTIAL'
    assert any('aggregate character ceiling' in row['error'] for row in result['failed_fetches'])


def test_sitemap_expiry_refuses_further_dns_work(monkeypatch) -> None:
    from security.url_safety import PublicURLClassificationBudget, URLClassificationLimit

    calls = []
    def resolver(host, port, **_kwargs):
        calls.append(host)
        time.sleep(.03)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', port))]

    monkeypatch.setattr(socket, 'getaddrinfo', resolver)
    budget = PublicURLClassificationBudget(timeout=.01)
    with pytest.raises(URLClassificationLimit):
        budget.validate('https://slow.example/')
    with pytest.raises(URLClassificationLimit):
        budget.validate('https://next.example/')
    assert calls == ['slow.example']


def test_crawl_unterminated_tag_feed_is_bounded() -> None:
    _bounded_python(
        "from integrations.product_proof.crawler import SiteCrawler; "
        "from integrations.technical.http import HttpHop; "
        "h=type('HTTP',(),{'get':lambda self,url:HttpHop(url,url,200,{},b'<img '*50000,1)})(); "
        "r=SiteCrawler(http=h)._page('https://example.com/',0,'example.com'); "
        "assert r.raw_html_available"
    )
