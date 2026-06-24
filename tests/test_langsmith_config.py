"""Tests for LangSmith config helpers."""

from __future__ import annotations

from observability.langsmith_config import invoke_config, tracing_enabled


def test_tracing_disabled_by_default_in_tests(monkeypatch) -> None:
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    assert tracing_enabled() is False

    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    assert tracing_enabled() is True


def test_invoke_config_sets_run_metadata() -> None:
    config = invoke_config(trigger="manual")
    assert config["run_name"] == "sentinel-manual"
    assert config["tags"] == ["sentinel", "manual"]
    assert config["metadata"]["trigger"] == "manual"
    assert config["metadata"]["service"] == "sentinel"
    assert config["metadata"]["run_id"]
