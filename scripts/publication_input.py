"""Captured input bytes are inert evidence, never publisher filesystem paths."""

import hashlib
import json
from pathlib import PurePosixPath, PureWindowsPath

from integrations.extensions.indexnow import normalize
from scripts.publication_subject import (
    JsonObject,
    exact_keys,
    object_value,
    sha_value,
    string_value,
)
from scripts.publication_targets import normalize_target

INPUT_KEYS = {"kind", "candidate_commit", "prepared_subject_sha256", "argument_path", "format", "content", "sha256"}


def _input_record(value: object, argument_path: str, candidate: str, digest: str) -> JsonObject:
    record = object_value(value, "captured command input")
    exact_keys(record, INPUT_KEYS, "captured command input")
    if (record["kind"] != "command_input" or record["candidate_commit"] != candidate
            or record["prepared_subject_sha256"] != digest or record["argument_path"] != argument_path):
        raise ValueError("Captured input is not bound to this actual command/source/subject")
    path = string_value(record["argument_path"], "captured input argument")
    if "\x00" in path:
        raise ValueError("Captured input argument contains a NUL")
    return record


def _input_format(path: str, platform: str) -> str:
    if platform not in {"ubuntu", "windows"}:
        raise ValueError("Captured input requires its authenticated source platform")
    path_type = PurePosixPath if platform == "ubuntu" else PureWindowsPath
    return "urls-json" if path_type(path).suffix.lower() == ".json" else "urls-text"


def captured_urls(value: object, *, argument_path: str, candidate: str, digest: str,
                  platform: str) -> JsonObject:
    record = _input_record(value, argument_path, candidate, digest)
    path = str(record["argument_path"])
    content = record["content"]
    if not isinstance(content, str) or not 0 < len(content.encode("utf-8")) <= 5_000_000:
        raise ValueError("Captured input exceeds its source byte bound")
    if hashlib.sha256(content.encode("utf-8")).hexdigest() != sha_value(record["sha256"], 64, "input digest"):
        raise ValueError("Captured input bytes do not match their digest")
    expected_format = _input_format(path, platform)
    if record["format"] != expected_format:
        raise ValueError("Captured input format disagrees with actual source file selection")
    text = content.removeprefix("\ufeff")
    if expected_format == "urls-json":
        urls = json.loads(text)
        if not isinstance(urls, list) or not all(isinstance(url, str) for url in urls):
            raise ValueError("Actual JSON URL input must be a string array")
    else:
        urls = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    checked = normalize(urls)
    return normalize_target({"kind": "indexnow_url_set", "values": list(checked.urls)})
