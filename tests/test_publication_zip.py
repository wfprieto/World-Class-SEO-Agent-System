"""In-memory adversarial ZIPs; no real artifact, provider or authorization data."""

from __future__ import annotations

import hashlib
import struct
import tracemalloc
import zipfile
import zlib
from io import BytesIO, UnsupportedOperation

import pytest

from scripts import publication_policy as policy
from scripts.publication_artifacts import inspect_result, unpack_candidate, unpack_result
from tests.test_publication_artifacts import NOW, bundle_files, zip_bytes


def central_offsets(raw):
    end = raw.rfind(b"PK\x05\x06")
    position = struct.unpack_from("<L", raw, end + 16)[0]
    while position < end:
        name_size, extra_size, comment_size = struct.unpack_from("<3H", raw, position + 28)
        name = raw[position + 46:position + 46 + name_size].decode("ascii")
        yield name, position
        position += 46 + name_size + extra_size + comment_size


def forged_expansion(files, name, *, tail_bytes=8 * 1024 * 1024):
    prefix = files[name]
    raw = bytearray(zip_bytes({**files, name: prefix + b"0" * tail_bytes}))
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        local = archive.getinfo(name).header_offset
    central = dict(central_offsets(raw))[name]
    for offset in (local + 14, central + 16):
        struct.pack_into("<L", raw, offset, zlib.crc32(prefix))
    for offset in (local + 22, central + 24):
        struct.pack_into("<L", raw, offset, len(prefix))
    return bytes(raw)


def inspect(raw, name="execution.json"):
    return inspect_result(raw, expected_archive_sha256=hashlib.sha256(raw).hexdigest(), member_name=name)


@pytest.mark.parametrize("name", ["execution.json", "publication-completion.json"])
def test_public_result_rejects_real_expansion_hidden_by_forged_small_size_and_prefix_crc(name):
    raw = forged_expansion({name: b"{}"}, name)
    with pytest.raises(ValueError):
        inspect(raw, name)


def test_public_candidate_rejects_the_same_forgery_before_expanding_oversized_payload(monkeypatch):
    files = bundle_files()
    name = next(name for name in files if name.endswith(".whl"))
    raw = forged_expansion(files, name)
    monkeypatch.setattr(policy, "MAX_MEMBER_BYTES", 1024 * 1024)
    with pytest.raises(ValueError):
        unpack_candidate(raw, expected_archive_sha256=hashlib.sha256(raw).hexdigest(), now=NOW)


def test_pinned_execution_result_cannot_accept_a_forged_truncated_prefix_hash():
    raw = forged_expansion({"execution.json": b"{}"}, "execution.json")
    with pytest.raises(ValueError):
        unpack_result(raw, expected_archive_sha256=hashlib.sha256(raw).hexdigest(),
                      member_name="execution.json", member_sha256=hashlib.sha256(b"{}").hexdigest())


def test_forged_eight_megabyte_stream_is_rejected_with_small_peak_actual_allocation():
    raw = forged_expansion({"execution.json": b"{}"}, "execution.json")
    tracemalloc.start()
    try:
        with pytest.raises(ValueError):
            inspect(raw)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 512 * 1024, f"forged two-byte member allocated {peak} traced bytes"


class NonSeekable(BytesIO):
    def seek(self, *args):
        raise UnsupportedOperation("controlled streaming ZIP fixture")


def ordinary(payload=b"{}", *, method=zipfile.ZIP_DEFLATED, streamed=False, wide=False):
    stream = NonSeekable() if streamed else BytesIO()
    with (zipfile.ZipFile(stream, "w", compression=method) as archive,
          archive.open("execution.json", "w", force_zip64=wide) as member):
        member.write(payload)
    return stream.getvalue()


def change_compressed(raw, transform):
    """Keep all 32-bit record boundaries honest while replacing only real stream bytes."""
    before = bytearray(raw)
    names, extras = struct.unpack_from("<HH", before, 26)
    start = 30 + names + extras
    size = struct.unpack_from("<L", before, 18)[0]
    previous_central = struct.unpack_from("<L", before, len(before) - 6)[0]
    changed = transform(bytes(before[start:start + size]))
    delta = len(changed) - size
    result = before[:start] + changed + before[start + size:]
    central = previous_central + delta
    struct.pack_into("<L", result, 18, len(changed))
    struct.pack_into("<L", result, central + 20, len(changed))
    struct.pack_into("<L", result, len(result) - 6, central)
    return bytes(result)


def remove_descriptor_signature(raw):
    result = bytearray(raw)
    central = dict(central_offsets(raw))["execution.json"]
    descriptor = result.rfind(b"PK\x07\x08", 0, central)
    del result[descriptor:descriptor + 4]
    struct.pack_into("<L", result, len(result) - 6, central - 4)
    return bytes(result)


@pytest.mark.parametrize("method", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
@pytest.mark.parametrize("streamed,wide", [(False, False), (True, False), (False, True), (True, True)])
def test_stdlib_generated_stored_deflate_local_zip64_and_stream_descriptors_remain_valid(method, streamed, wide):
    raw = ordinary(method=method, streamed=streamed, wide=wide)
    assert inspect(raw) == b"{}"


@pytest.mark.parametrize("method", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
@pytest.mark.parametrize("wide", [False, True])
def test_valid_stream_descriptor_without_optional_signature_is_supported(method, wide):
    raw = remove_descriptor_signature(ordinary(method=method, streamed=True, wide=wide))
    assert inspect(raw) == b"{}"


@pytest.mark.parametrize("method", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_stdlib_generated_global_zip64_directory_remains_bounded_and_valid(monkeypatch, method):
    with monkeypatch.context() as settings:
        settings.setattr(zipfile, "ZIP64_LIMIT", 1)
        raw = ordinary(method=method, streamed=True, wide=True)
    assert b"PK\x06\x06" in raw and b"PK\x06\x07" in raw
    assert inspect(raw) == b"{}"


@pytest.mark.parametrize("limit", [64, 65536, 65537, 1048576])
def test_true_json_expansion_at_exact_limit_and_inflate_chunk_boundary_is_accepted(monkeypatch, limit):
    payload = b'{"x":"' + b"a" * (limit - 8) + b'"}'
    assert len(payload) == limit
    monkeypatch.setattr(policy, "MAX_RECORD_BYTES", limit)
    assert inspect(ordinary(payload)) == payload


@pytest.mark.parametrize("method", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_true_one_byte_over_limit_is_rejected(monkeypatch, method):
    monkeypatch.setattr(policy, "MAX_RECORD_BYTES", 64)
    with pytest.raises(ValueError):
        inspect(ordinary(b'{"x":"' + b"a" * 57 + b'"}', method=method))


def test_forged_one_byte_over_small_actual_limit_is_rejected_not_silently_truncated(monkeypatch):
    prefix = b'{"x":"' + b"a" * 56 + b'"}'
    monkeypatch.setattr(policy, "MAX_RECORD_BYTES", 64)
    with pytest.raises(ValueError):
        inspect(forged_expansion({"execution.json": prefix}, "execution.json", tail_bytes=1))


@pytest.mark.parametrize("mutation", ["truncated", "empty", "junk-tail", "second-stream", "corrupt"])
def test_true_deflate_end_and_exact_compressed_range_are_required(mutation):
    def corrupt(data):
        if mutation == "truncated":
            return data[:-1]
        if mutation == "empty":
            return b""
        if mutation == "junk-tail":
            return data + b"hidden-compressed-tail"
        if mutation == "second-stream":
            compressor = zlib.compressobj(wbits=-15)
            return data + compressor.compress(b"second payload") + compressor.flush()
        return b"\xff" + data[1:]

    with pytest.raises(ValueError):
        inspect(change_compressed(ordinary(), corrupt))


@pytest.mark.parametrize("offset,value,code", [(8, 0, "H"), (6, 2, "H"), (14, 0, "L"), (22, 3, "L")])
def test_local_and_central_method_flags_crc_and_size_must_agree(offset, value, code):
    raw = bytearray(ordinary())
    struct.pack_into("<" + code, raw, offset, value)
    with pytest.raises(ValueError):
        inspect(bytes(raw))


def test_actual_crc_is_checked_even_when_local_and_central_metadata_agree():
    raw = bytearray(ordinary())
    central = dict(central_offsets(raw))["execution.json"]
    for offset in (14, central + 16):
        struct.pack_into("<L", raw, offset, 0)
    with pytest.raises(ValueError):
        inspect(bytes(raw))


@pytest.mark.parametrize("wide", [False, True])
def test_stream_descriptor_actual_crc_and_sizes_cannot_disagree_with_metadata(wide):
    raw = bytearray(ordinary(streamed=True, wide=wide))
    descriptor = raw.index(b"PK\x07\x08")
    struct.pack_into("<L", raw, descriptor + 4, 0)
    with pytest.raises(ValueError):
        inspect(bytes(raw))


def test_hidden_unaccounted_bytes_between_payload_and_directory_are_rejected():
    raw = bytearray(ordinary())
    central = dict(central_offsets(raw))["execution.json"]
    raw[central:central] = b"hidden-tail"
    struct.pack_into("<L", raw, len(raw) - 6, central + len(b"hidden-tail"))
    with pytest.raises(ValueError):
        inspect(bytes(raw))


def test_unknown_compression_is_rejected_without_trying_a_fallback():
    raw = bytearray(ordinary())
    central = dict(central_offsets(raw))["execution.json"]
    struct.pack_into("<H", raw, 8, 99)
    struct.pack_into("<H", raw, central + 10, 99)
    with pytest.raises(ValueError):
        inspect(bytes(raw))


def test_stored_candidate_payload_set_is_preserved():
    stream = BytesIO()
    files = bundle_files()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    raw = stream.getvalue()
    _, actual = unpack_candidate(raw, expected_archive_sha256=hashlib.sha256(raw).hexdigest(), now=NOW)
    assert actual == files
