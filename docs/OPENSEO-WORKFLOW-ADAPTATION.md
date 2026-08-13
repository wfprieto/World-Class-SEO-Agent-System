# OpenSEO Workflow Adaptation

This document records the clean-room workflow patterns adapted from OpenSEO-style tooling.

## Adapted Patterns

- Free-first evidence before paid APIs.
- Explicit budget and credential gates for metered SEO data.
- Saved keyword and rank-tracking concepts as workflow state, not ranking truth.
- Backlink and mention data as evidence requiring relevance, risk, and compliance filters.
- Tool evidence merging that separates first-party observed data from third-party estimates.

## Non-Goals

- No external OpenSEO prose or source code is copied.
- No vendor-specific schema becomes canonical runtime state.
- No paid tool is required for baseline operation.
- No third-party metric is treated as exact ground truth.

## Affected FLOW Stages

- Find: cost-aware keyword and SERP data planning.
- Leverage: cost-aware link prospecting and authority-gap planning.
- Optimize: evidence merge across first-party exports, third-party estimates, and manual observations.

## Verification

The adapted workflows are tested in `tests/test_openseo_workflow_expansion.py` and remain connected through
the existing `flow-prompt-run` skill.
