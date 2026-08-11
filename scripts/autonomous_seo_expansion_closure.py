"""Compatibility facade for autonomous SEO closure validation."""

from scripts.autonomous_seo_phase_closure import (
    PROGRAM_RELATIVE,
    canonical_hash,
    closure_evidence_payload,
    closure_hash_errors,
    closure_path,
    evidence_ref_errors,
    field_bounded_transition_errors,
    file_sha256,
    git_command_ok,
    git_stdout,
    load_object,
    phase_closure_errors,
    reviewer_file_errors,
    reviewer_independence_errors,
    safe_repo_path,
    schema_errors,
)
from scripts.autonomous_seo_program_closure import program_closure_errors

__all__ = [
    "PROGRAM_RELATIVE",
    "canonical_hash",
    "closure_evidence_payload",
    "closure_hash_errors",
    "closure_path",
    "evidence_ref_errors",
    "field_bounded_transition_errors",
    "file_sha256",
    "git_command_ok",
    "git_stdout",
    "load_object",
    "phase_closure_errors",
    "program_closure_errors",
    "reviewer_file_errors",
    "reviewer_independence_errors",
    "safe_repo_path",
    "schema_errors",
]
