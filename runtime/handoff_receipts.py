"""Deterministic handoff integrity receipts for the bounded runtime boundary."""
from __future__ import annotations

import hmac
import json
from dataclasses import asdict
from hashlib import sha256

from runtime.state import Handoff


def terminal_handoff_receipt(handoff: Handoff) -> str:
    """Hash canonical runtime fields for mutation detection, not identity trust."""
    fields = {
        key: value
        for key, value in asdict(handoff).items()
        if key != "terminal_receipt"
    }
    encoded = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def seal_terminal_handoff(handoff: Handoff) -> None:
    handoff.terminal_receipt = terminal_handoff_receipt(handoff)


def terminal_receipt_is_valid(handoff: Handoff) -> bool:
    return bool(handoff.terminal_receipt) and hmac.compare_digest(
        handoff.terminal_receipt, terminal_handoff_receipt(handoff)
    )
