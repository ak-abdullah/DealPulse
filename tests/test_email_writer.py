"""Tests for email body normalization."""

from __future__ import annotations

from agents.email_writer import _normalize_body


def test_normalize_body_splits_one_line_llm_output() -> None:
    raw = (
        "Hi Alex, I wanted to follow up on our meeting. Are we still on track to move "
        "forward as discussed? Can we schedule a quick call this week? "
        "Best, Abdullah Khalid"
    )
    body = _normalize_body(raw, "Abdullah Khalid")

    assert body.startswith("Hi Alex,\n\n")
    assert "Can we schedule a quick call this week?" in body
    assert body.endswith("Best,\nAbdullah Khalid")
    assert "\n\n" in body


def test_normalize_body_preserves_existing_paragraphs() -> None:
    raw = "Hi Alex,\n\nThanks for your time.\n\nBest,\nAbdullah Khalid"
    body = _normalize_body(raw, "Abdullah Khalid")
    assert "Thanks for your time." in body
    assert "Best,\nAbdullah Khalid" in body
