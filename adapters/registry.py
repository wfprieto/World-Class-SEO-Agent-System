"""Neutral adapter contracts; concrete factories live in seoctl.composition."""

from contracts.adapter import AdapterNotConfigured, AdapterResult, RuntimeAdapter

__all__ = ["AdapterNotConfigured", "AdapterResult", "RuntimeAdapter"]
