"""Pipeline monitor node: load stalled deals from HubSpot."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from config.settings import settings
from graph.state import AgentState
from tools.hubspot import HubSpotIntegrationError, get_stalled_deals

LOGGER = logging.getLogger(__name__)


def _fresh_run_defaults() -> dict[str, Any]:
    """Reset per-run collections so a new monitor pass starts clean."""
    return {
        "current_deal_index": 0,
        "research_reports": {},
        "deal_scores": {},
        "drafted_emails": {},
    }


def pipeline_monitor_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph node: fetch stalled deals and update shared state.

    Returns a partial state dict; LangGraph merges it into ``AgentState``.
    """
    LOGGER.info(
        "Checking pipeline for stalled deals (threshold=%s days)",
        settings.stale_deal_days,
    )

    run_meta = {
        "run_id": str(uuid.uuid4()),
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        **_fresh_run_defaults(),
    }

    try:
        stalled = get_stalled_deals(settings.stale_deal_days)
    except HubSpotIntegrationError:
        LOGGER.exception("HubSpot integration error")
        return {
            **run_meta,
            "stalled_deals": [],
            "should_continue": False,
            "errors": ["pipeline_monitor: HubSpot request failed (see logs)"],
        }
    except Exception as exc:  # noqa: BLE001 — surface unexpected failures on the node
        LOGGER.exception("Unexpected error in pipeline_monitor")
        return {
            **run_meta,
            "stalled_deals": [],
            "should_continue": False,
            "errors": [f"pipeline_monitor: {exc}"],
        }

    stalled.sort(key=lambda deal: deal.deal_value, reverse=True)
    LOGGER.info("Found %s stalled deals", len(stalled))

    return {
        **run_meta,
        "stalled_deals": stalled,
        "should_continue": len(stalled) > 0,
    }
