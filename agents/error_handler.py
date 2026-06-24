"""Error handler node: central place to review and record pipeline failures."""

from __future__ import annotations

import logging
from typing import Any

from graph.router import executor_progress
from graph.state import AgentState

LOGGER = logging.getLogger(__name__)

_SEND_OUTCOMES = (
    "sent_email:",
    "skipped_send:",
    "skipped_duplicate:",
    "failed_send:",
)


def _errors_for_deal(errors: list[str], deal_id: str) -> list[str]:
    token = f":{deal_id}"
    return [message for message in errors if token in message]


def error_handler_node(state: AgentState) -> dict[str, Any]:
    """
    Review the deal just processed by the executor.

    Runs once after every executor visit. Logs failures in one place and
    records ``handled_error:<deal_id>`` so the graph can move on cleanly.
    """
    progress = executor_progress(state)
    if progress == 0:
        return {}

    deal = state.stalled_deals[progress - 1]
    deal_id = deal.deal_id
    company = deal.company_name or deal_id

    last_action = next(
        (action for action in reversed(state.actions_taken) if action.startswith(_SEND_OUTCOMES)),
        "",
    )
    deal_errors = _errors_for_deal(state.errors, deal_id)

    if last_action.startswith("sent_email:"):
        LOGGER.debug("Error handler: %s sent successfully", company)
        return {}

    if last_action.startswith("skipped_duplicate:"):
        LOGGER.info(
            "Error handler: duplicate follow-up skipped for %s (CRM note exists)",
            company,
        )
        return {}

    if last_action.startswith("skipped_send:"):
        LOGGER.warning(
            "Error handler: skipped send for %s (%s)",
            company,
            "; ".join(deal_errors) or "no details",
        )
    elif last_action.startswith("failed_send:"):
        LOGGER.error(
            "Error handler: send failed for %s (%s)",
            company,
            "; ".join(deal_errors) or "no details",
        )
    elif deal_errors:
        LOGGER.error(
            "Error handler: unresolved errors for %s — %s",
            company,
            "; ".join(deal_errors),
        )
    else:
        return {}

    return {"actions_taken": [f"handled_error:{deal_id}"]}
