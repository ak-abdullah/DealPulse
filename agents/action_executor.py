"""Action executor node: send drafted email and log note on HubSpot deal."""

from __future__ import annotations

import logging
from typing import Any

from graph.state import AgentState, DealInfo
from tools.gmail import GmailIntegrationError, send_email
from tools.hubspot import HubSpotIntegrationError, add_deal_note

LOGGER = logging.getLogger(__name__)


def _executor_index(state: AgentState) -> int:
    prefixes = ("sent_email:", "skipped_send:", "failed_send:")
    return sum(1 for action in state.actions_taken if action.startswith(prefixes))


def _build_note(deal: DealInfo, subject: str, gmail_id: str) -> str:
    company = deal.company_name or deal.deal_id
    return (
        f"DealPulse automated follow-up sent to {deal.contact_email} "
        f"({company}).\n"
        f"Subject: {subject}\n"
        f"Gmail message id: {gmail_id}"
    )


def action_executor_node(state: AgentState) -> dict[str, Any]:
    """Send one drafted email and log a HubSpot note (next unsent deal)."""
    idx = _executor_index(state)
    deals = state.stalled_deals

    if idx >= len(deals):
        LOGGER.info("Executor: no remaining deals (index=%s)", idx)
        return {}

    deal = deals[idx]
    company = deal.company_name or deal.deal_id
    draft = state.drafted_emails.get(deal.deal_id, {})
    subject = (draft.get("subject") or "").strip()
    body = (draft.get("body") or "").strip()

    LOGGER.info("Executing actions for deal %s (%s)", deal.deal_id, company)

    update: dict[str, Any] = {}

    if not subject or not body:
        update["errors"] = [
            f"action_executor:{deal.deal_id}: missing email subject or body"
        ]
        update["actions_taken"] = [f"skipped_send:{deal.deal_id}"]
        return update

    if not deal.contact_email.strip():
        update["errors"] = [
            f"action_executor:{deal.deal_id}: contact has no email address"
        ]
        update["actions_taken"] = [f"skipped_send:{deal.deal_id}"]
        return update

    try:
        gmail_id = send_email(
            to_email=deal.contact_email,
            subject=subject,
            body=body,
        )
        note_id = add_deal_note(deal.deal_id, _build_note(deal, subject, gmail_id))
        update["actions_taken"] = [
            f"sent_email:{deal.deal_id}",
            f"crm_note:{deal.deal_id}:{note_id}",
        ]
        LOGGER.info("Completed actions for %s", company)
    except (GmailIntegrationError, HubSpotIntegrationError) as exc:
        LOGGER.exception("Action executor failed for deal %s", deal.deal_id)
        update["errors"] = [f"action_executor:{deal.deal_id}: {exc}"]
        update["actions_taken"] = [f"failed_send:{deal.deal_id}"]

    return update
