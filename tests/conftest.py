"""Shared fixtures and env defaults for tests."""

from __future__ import annotations

import os

# Settings are validated at import time; tests must not require a real .env file.
os.environ.setdefault("HUBSPOT_API_KEY", "test-hubspot-key")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("HUBSPOT_USE_MOCK", "true")
os.environ.setdefault("GMAIL_USE_MOCK", "true")

import pytest

from tools import hubspot as hubspot_tools


@pytest.fixture(autouse=True)
def reset_hubspot_mock_state() -> None:
    hubspot_tools._mock_followup_deals.clear()
    yield
    hubspot_tools._mock_followup_deals.clear()
