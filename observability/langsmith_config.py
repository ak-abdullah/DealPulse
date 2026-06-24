"""LangSmith / LangChain tracing helpers."""

from __future__ import annotations

import os
import uuid


def tracing_enabled() -> bool:
    return os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("1", "true", "yes")


def invoke_config(*, trigger: str) -> dict:
    """Runnable config passed to ``pipeline.invoke`` for LangSmith run metadata."""
    run_id = str(uuid.uuid4())
    return {
        "run_name": f"sentinel-{trigger}",
        "metadata": {
            "trigger": trigger,
            "run_id": run_id,
            "service": "sentinel",
        },
        "tags": ["sentinel", trigger],
    }
