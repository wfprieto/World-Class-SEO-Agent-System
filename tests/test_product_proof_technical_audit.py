from __future__ import annotations
import json
from pathlib import Path
from datetime import date

from integrations.product_proof.crawler import RobotsPolicy, parse_robots
from integrations.product_proof.service import ProductProofTechnicalAudit
from scripts.validate_seo_claims import validate
from seoctl.audit_cli import run

ROOT = Path(__file__).resolve().parents[1]


def _fixture(tmp_path: Path) -> Path:
    payload = {
      'responses': {
        'https://example.com/': {
          'status_code': 200,
          'headers': {'Content-Type':'text/html; charset=utf-8'},
          'body': '''<html><head><title>Home</title><link rel="canonical" href="https://example.com/">
          <meta name="robots" content="nosnippet"></head><body><h1>Home</h1>
          <img src="https://cdn.example.com/hero.webp" loading="lazy" alt="Hero">
          <a href="/?page=2">Page 2</a><a href="/missing">Missing</a>
          <a href="/facet?color=green">Green</a><a href="/private">Private</a></body></html>'''
        },
        'https://example.com/?page=2': {
          'status_code': 200,'headers': {'Content-Type':'text/html'},
          'body': '<html><head><title>Page 2</title><link rel="canonical" href="https://example.com/"><link rel="next" href="?page=3"></head><body><h1>Page 2</h1><p>Substantial page content is present here.</p></body></html>'
        },
        'https://example.com/missing': {
          'status_code': 404,'headers': {'Content-Type':'text/html'},
          'body': '<html><title>Not found</title><body>Page not found</body></html>'
        },
        'https://example.com/facet?color=green': {
          'status_code': 200,'headers': {'Content-Type':'text/html'},
          'body': '<html><title>No results</title><body>No results</body></html>'
        },
        'https://example.com/private': {
          'status_code': 200,'headers': {'Content-Type':'text/html'},
          'body': '<html><head><title>Private</title><meta name="robots" content="noindex"></head><body>Private profile content.</body></html>'
        },
        'https://example.com/robots.txt': {
          'status_code': 200,'headers': {'Content-Type':'text/plain'},
          'body': 'User-agent: *\nDisallow: /private\nCrawl-delay: 10\nSitemap: https://example.com/sitemap.xml\n'
        },
        'https://cdn.example.com/robots.txt': {
          'status_code': 500,'headers': {'Content-Type':'text/plain'},'body': 'server error'
        }
      }
    }
    path=tmp_path/'fixture.json'; path.write_text(json.dumps(payload),encoding='utf-8'); return path


def test_robots_longest_match_and_least_restrictive_tie():
    groups,_,_=parse_robots('User-agent: *\nDisallow: /folder\nAllow: /folder\nDisallow: /\nAllow: /public\n')
    policy=RobotsPolicy(groups)
    assert policy.allowed('https://example.com/folder') is True
    assert policy.allowed('https://example.com/public/page') is True
    assert policy.allowed('https://example.com/private') is False


def test_claim_registry_and_deprecations_validate():
    assert validate(ROOT, as_of=date(2026,7,12)) == []


def test_flagship_fixture_audit_generates_client_artifacts(tmp_path: Path):
    fixture=_fixture(tmp_path)
    out=tmp_path/'out'
    result=ProductProofTechnicalAudit(claim_registry=ROOT/'knowledge/seo-claim-registry.json').run(
      url='https://example.com/', output_dir=out, fixture_path=fixture,
      max_urls=20,max_depth=3,max_asset_hosts=5)
    assert result.status == 'complete'
    assert result.data['pages_crawled'] == 5
    assert result.data['agents_executed'] == 7
    assert result.data['trust_summary']['unsupported_material_findings'] == 0
    findings=json.loads((out/'findings.json').read_text())
    ids={row['id'].split('-')[0] for row in findings}
    titles='\n'.join(row['title'] for row in findings)
    assert 'robots.txt returns a server-error response' in titles
    assert 'Paginated pages canonicalize to page one' in titles
    assert 'Pages carry noindex instructions that Google may be unable to read' in titles
    assert 'Early page images are lazy-loaded' in titles
    assert 'Empty faceted combinations return successful responses' in titles
    for name in ('run-manifest.json','technical-audit.md','executive-summary.md','remediation-plan.csv','verification-plan.json','agent-contributions.json'):
      assert (out/name).is_file() and (out/name).stat().st_size > 0
    manifest=json.loads((out/'run-manifest.json').read_text())
    assert manifest['evidence_mode']=='FIXTURE'
    assert manifest['fixture_is_live_proof'] is False
    assert manifest['multi_agent_contribution']['decisions_recorded'] >= 1


def test_cli_claims_and_audit_fixture(tmp_path: Path):
    claims, code = run(['knowledge','claims','--evidence-class','UNVERIFIED'])
    assert code == 0
    assert claims['data']['count'] >= 2
    check, code = run(['knowledge','validate'])
    assert code == 0 and check['status']=='ok'
    fixture=_fixture(tmp_path)
    payload, code = run(['audit','technical','--url','https://example.com/','--output',str(tmp_path/'cli'),'--fixture',str(fixture),'--max-urls','20'])
    assert code == 0
    assert payload['data']['agents_executed'] == 7


def test_capability_overlay_preserves_packages_and_adds_source_contract(tmp_path: Path):
    from runtime.capability_resolver import CapabilityResolver
    repo = tmp_path/'repo'
    for folder in ('orchestration','skills','knowledge','agents','templates'):
        (repo/folder).mkdir(parents=True,exist_ok=True)
    (repo/'SYSTEM_SPEC.md').write_text('# System')
    (repo/'knowledge/seo-quality-gates.md').write_text('# Gates')
    (repo/'orchestration/capability-registry.json').write_text(json.dumps({
      'shared':{},
      'agents':{
        'SEO Technical Agent':{
          'agent_file':'agents/tech.md','skills':['technical-audit'],
          'skill_files':['skills/core.md'],'knowledge_files':['knowledge/base.md'],
          'templates':['templates/audit.md'],'required_evidence':['url']
        }
      }
    }))
    (repo/'skills/package-registry.json').write_text(json.dumps({
      'package_document':'skills/packages.md','packages':{'technical-audit':{}}
    }))
    overlay=json.loads((ROOT/'orchestration/product-proof-capability-overlay.json').read_text())
    (repo/'orchestration/product-proof-capability-overlay.json').write_text(json.dumps(overlay))
    files={
      'agents/tech.md':'# Tech', 'skills/core.md':'# Core', 'skills/packages.md':'# Packages',
      'skills/product-proof-technical-audit.md':'# Product',
      'skills/deep-skill-procedures.md':'## technical-audit\nbase',
      'skills/product-proof-procedures.md':'## product-proof-technical-audit\nproduct',
      'knowledge/base.md':'base', 'knowledge/seo-claim-registry.json':'{}',
      'knowledge/deprecation-registry.json':'{}','knowledge/primary-source-technical-seo.md':'source',
      'templates/audit.md':'template',
      'knowledge/source-assets/core-web-vitals-remediation.md':'cwv',
      'knowledge/source-assets/ai-search-and-retrieval.md':'ai',
      'knowledge/source-assets/content-information-gain.md':'content',
      'knowledge/source-assets/authority-brand-and-links.md':'authority',
      'knowledge/source-assets/local-reviews-compliance.md':'local',
      'knowledge/source-assets/client-reporting-roi.md':'reporting',
      'knowledge/source-assets/measurement-and-attribution.md':'measurement'
    }
    for relative, content in files.items():
      path=repo/relative; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content)
    resolver=CapabilityResolver(repo)
    bundle=resolver.bundle('SEO Technical Agent')
    assert 'technical-audit' in bundle.skills
    assert 'product-proof-technical-audit' in bundle.skills
    assert 'skills/packages.md' in bundle.skill_files
    assert 'knowledge/seo-claim-registry.json' in bundle.knowledge_files
    report=resolver.validate()
    assert report['package_count']==1
    assert report['product_proof_agent_count']==1


def test_product_proof_program_validator():
    from scripts.validate_product_proof_program import validate as validate_program
    result=validate_program(ROOT)
    assert result['status']=='PASS'
    assert len(result['passes'])==20
    assert result['release_approved'] is False


def test_ai_timeout_citation_review_and_reporting_intelligence(tmp_path: Path):
    from integrations.product_proof.intelligence import (
        AITimeoutAnalyzer, AICitationOpportunityAnalyzer,
        ReviewComplianceAnalyzer, PerformanceNarrativeAnalyzer,
    )
    log = tmp_path / 'access.log'
    log.write_text(
        '203.0.113.10 - - [12/Jul/2026:10:00:00 -0400] "GET /pricing HTTP/1.1" 499 0 "-" "ChatGPT-User/1.0" request_time=3.200\n'
        '203.0.113.11 - - [12/Jul/2026:10:00:01 -0400] "GET /guide HTTP/1.1" 200 1200 "-" "PerplexityBot/1.0" request_time=0.220\n',
        encoding='utf-8'
    )
    timeout = AITimeoutAnalyzer().analyze(log_path=log, server_stack='nginx')
    assert timeout.data['ai_requests'] == 2
    assert timeout.data['timeout_499_count'] == 1
    observations = tmp_path / 'observations.json'
    observations.write_text(json.dump({'observeations':[
        {'observed_at':'2026-07-12','platform':'Google AI Overview','prompt':'best technical seo audit','aio_present':True,'organic_position':4,'cited':False,'competitors_cited':['Competitor A']},
        {'observed_at':'2026-07-12','platform':'Perplexity','prompt':'technical seo governance','aio_present':False,'organic_position':2,'cited':True,'linked':True,'recommendation_state':'RECOMMENDED','narrative_accuracy':'ACCURATE'}
    ]}), encoding='utf-8')
    citation = AICitationOpportunityAnalyzer().analyze(observations_path=observations)
    assert citation.data['unowned_count'] == 1
    review = tmp_path / 'reviews.json'
    review.write_text(json.dumps({'practices':{'review_kiosk':True,'owner_response_rate':0.4}}),encoding='utf-8')
    screened = ReviewComplianceAnalyzer().analyze(input_path=review)
    assert screened.data['finding_count'] == 2
    performance = tmp_path / 'performance.json'
    performance.write_text(json.dumps({'metric':'qualified leads','baseline':10,'target':12,'actual':14,'unit':'','better_direction':'higher','target_set_before_period':True,'lead_value':500,'close_rate':0.25,'cost':1000,'observed':{'leads':14},'proxy':{},'modeled':{'expected_value':1750}}),encoding='utf-8')
    narrative = PerformanceNarrativeAnalyzer().analyze(input_path=performance)
    assert narrative.data['target_met'] is True
    assert narrative.data['estimated_value'] == 1750


def test_intelligence_cli_commands(tmp_path: Path):
    from seoctl.intelligence_cli import run as intelligence_run
    log=tmp_path/'access.log'
    log.write_text('203.0.113.10 - - [12/Jul/2026:10:00:00 -0400] "GET / HTTP/1.1" 499 0 "-" "ChatGPT-User/1.0" request_time=2.0\n')
    payload, code = intelligence_run(['intelligence','ai-timeouts','--log',str(log),'--server-stack','nginx'])
    assert code == 0 and payload['data']['timeout_499_count'] == 1


def test_product_claim_inventory_remains_truthful():
    from scripts.validate_product_claims import validate as validate_product_claims
    assert validate_product_claims(ROOT) == []
    payload, code = run(['knowledge','product-claims','--status','BLOCKED'])
    assert code == 0
    assert {row['id'] for row in payload['data']['claims']} == {'production-ready','best-in-world'}
