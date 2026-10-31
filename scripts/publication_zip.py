"""Strict ZIP ranges and genuinely bounded inflation, never ZipExtFile truncation.

Only STORED/raw-DEFLATED members are supported. Metadata comes from ZipFile,
but local sizes, descriptors, contiguous ranges, real stream EOF, actual output
length and CRC are independently checked. Each inflate call emits <=64KiB and
at most the remaining declared/actual policy budget plus one detection byte.
No decompressor flush, extraction, or payload-sized compressed slice is used.
"""

from __future__ import annotations

import struct
import zipfile
import zlib

CHUNK = 65536
SENTINEL = 0xFFFFFFFF


def _zip64_end(raw: bytes, end: int) -> tuple[int, int, int, int]:
    locator = end - 20
    if locator < 0 or raw[locator:locator + 4] != b"PK\x06\x07":
        raise ValueError("ZIP64 locator is missing")
    disk, offset, disks = struct.unpack_from("<LQL", raw, locator + 4)
    if disk or disks != 1 or offset + 56 != locator:
        raise ValueError("ZIP64 locator must identify one bounded single-disk directory")
    fields = struct.unpack_from("<4sQ2H2L4Q", raw, offset)
    signature, record_size, _, _, disk, start_disk, disk_count, count, size, start = fields
    if signature != b"PK\x06\x06" or record_size != 44 or disk or start_disk or disk_count != count:
        raise ValueError("ZIP64 directory is inconsistent or unsupported")
    return count, size, start, offset


def _directory_bounds(raw: bytes, end: int, count: int) -> tuple[int, int]:
    _, disk, start_disk, disk_count, total, size, start, comment = struct.unpack_from("<4s4H2LH", raw, end)
    if disk or start_disk or end + 22 + comment != len(raw):
        raise ValueError("archive must have exact single-disk boundaries")
    boundary = end
    if raw[max(0, end - 20):end - 16] == b"PK\x06\x07":
        actual_count, actual_size, actual_start, boundary = _zip64_end(raw, end)
        if (disk_count not in {actual_count, 0xFFFF} or total not in {actual_count, 0xFFFF}
                or size not in {actual_size, SENTINEL} or start not in {actual_start, SENTINEL}):
            raise ValueError("ZIP64 and legacy directory fields disagree")
        disk_count = total = actual_count
        size, start = actual_size, actual_start
    if disk_count != count or total != count or start + size != boundary:
        raise ValueError("archive must contain the exact bounded directory member count")
    return start, boundary


def directory_start(raw: bytes, count: int) -> int:
    """Validate bounded central records before ZipFile can allocate their metadata."""
    end = raw.rfind(b"PK\x05\x06", max(0, len(raw) - 65557))
    if end < 0 or end + 22 > len(raw):
        raise ValueError("archive has no bounded central directory")
    start, boundary = _directory_bounds(raw, end, count)
    cursor = start
    observed = 0
    while cursor < boundary:
        if cursor + 46 > boundary or raw[cursor:cursor + 4] != b"PK\x01\x02":
            raise ValueError("archive central directory is inconsistent")
        name_size, extra_size, comment_size = struct.unpack_from("<3H", raw, cursor + 28)
        cursor += 46 + name_size + extra_size + comment_size
        observed += 1
        if observed > count or cursor > boundary:
            raise ValueError("archive central directory exceeds its bound")
    if observed != count:
        raise ValueError("archive central directory member count disagrees")
    return start


def _extra_fields(extra: bytes) -> dict[int, bytes]:
    values: dict[int, bytes] = {}
    cursor = 0
    while cursor < len(extra):
        if cursor + 4 > len(extra):
            raise ValueError("ZIP extra field header is truncated")
        identifier, size = struct.unpack_from("<HH", extra, cursor)
        cursor += 4
        if identifier in values or cursor + size > len(extra):
            raise ValueError("ZIP extra field is duplicated or truncated")
        values[identifier] = extra[cursor:cursor + size]
        cursor += size
    return values


def _local_sizes(extra: bytes, size: int, compressed: int) -> tuple[int, int, bool]:
    fields = _extra_fields(extra)
    wide = fields.get(1, b"")
    position = 0
    result = []
    for value in (size, compressed):
        if value == SENTINEL:
            if position + 8 > len(wide):
                raise ValueError("local ZIP64 size is missing")
            value = struct.unpack_from("<Q", wide, position)[0]
            position += 8
        result.append(value)
    if len(wide) != position:
        raise ValueError("local ZIP64 size fields are ambiguous")
    return result[0], result[1], 1 in fields


def _descriptor(raw: bytes, start: int, end: int, info: zipfile.ZipInfo, wide: bool) -> None:
    size = 20 if wide else 12
    if end - start == size + 4 and raw[start:start + 4] == b"PK\x07\x08":
        start += 4
    if end - start != size:
        raise ValueError("ZIP descriptor boundary is missing, truncated or has hidden bytes")
    crc, compressed, actual = struct.unpack_from("<LQQ" if wide else "<LLL", raw, start)
    if (crc, compressed, actual) != (info.CRC, info.compress_size, info.file_size):
        raise ValueError("ZIP descriptor disagrees with the central member")


def _local_format(signature: bytes, flags: int, method: int, info: zipfile.ZipInfo) -> None:
    if (signature != b"PK\x03\x04" or flags != info.flag_bits or method != info.compress_type
            or flags & ~0x080E):
        raise ValueError("ZIP local compression or flags disagree with the central member")


def _member_range(raw: bytes, info: zipfile.ZipInfo, boundary: int) -> tuple[int, int]:
    offset = info.header_offset
    if not 0 <= offset < boundary <= len(raw) or offset + 30 > boundary:
        raise ValueError("ZIP local header range is invalid")
    fields = struct.unpack_from("<4s5H3L2H", raw, offset)
    signature, version, flags, method, _, _, crc, compressed, size, name_size, extra_size = fields
    _local_format(signature, flags, method, info)
    start = offset + 30 + name_size + extra_size
    if start > boundary or raw[offset + 30:offset + 30 + name_size] != info.filename.encode("ascii"):
        raise ValueError("ZIP local filename or extra field range is invalid")
    size, compressed, wide = _local_sizes(raw[offset + 30 + name_size:start], size, compressed)
    if wide and version < 45:
        raise ValueError("ZIP64 member requires the ZIP64 extraction version")
    end = start + info.compress_size
    if end > boundary:
        raise ValueError("ZIP compressed member overlaps its next record")
    if flags & 8:
        if crc not in {0, info.CRC} or compressed not in {0, info.compress_size} or size not in {0, info.file_size}:
            raise ValueError("streamed ZIP local sizes disagree with central metadata")
        _descriptor(raw, end, boundary, info, wide)
    elif (end != boundary or (crc, compressed, size) != (info.CRC, info.compress_size, info.file_size)):
        raise ValueError("ZIP local size/CRC or compressed boundary disagrees")
    return start, end


def _inflate(raw: bytes, start: int, end: int, limit: int) -> bytes:
    decoder = zlib.decompressobj(-zlib.MAX_WBITS)
    output = bytearray()
    cursor = start
    pending = b""
    while True:
        if not pending:
            pending = raw[cursor:min(end, cursor + CHUNK)]
            cursor += len(pending)
        prior = pending
        capacity = limit - len(output)
        piece = decoder.decompress(pending, min(CHUNK, capacity + 1))
        if len(piece) > capacity:
            raise ValueError("ZIP actual expansion exceeds declared size or remaining byte budget")
        output.extend(piece)
        pending = decoder.unconsumed_tail
        if decoder.eof:
            if pending or decoder.unused_data or cursor != end:
                raise ValueError("ZIP stream has trailing or unused compressed bytes")
            return bytes(output)
        if not piece and (pending == prior or (not pending and cursor == end)):
            raise ValueError("ZIP deflate stream is unfinished or cannot progress")


def read_member(raw: bytes, info: zipfile.ZipInfo, *, boundary: int, limit: int) -> bytes:
    """Read exactly one checked member within an actual remaining output budget."""
    if not 0 < info.file_size <= limit:
        raise ValueError("ZIP member exceeds its remaining actual byte budget")
    start, end = _member_range(raw, info, boundary)
    if info.compress_type == zipfile.ZIP_STORED:
        if info.compress_size != info.file_size:
            raise ValueError("stored ZIP compressed/actual length mismatch")
        output = raw[start:end]
    elif info.compress_type == zipfile.ZIP_DEFLATED:
        output = _inflate(raw, start, end, min(limit, info.file_size))
    else:
        raise ValueError("ZIP compression algorithm is unsupported")
    if len(output) != info.file_size or zlib.crc32(output) != info.CRC:
        raise ValueError("ZIP actual member size or CRC integrity mismatch")
    return output
