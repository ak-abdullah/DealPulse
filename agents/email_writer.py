"""Email writer node: Groq drafts a follow-up from research."""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from config.settings import settings
from graph.state import AgentState, DealInfo
from prompts.writer_prompt import WRITER_SYSTEM_PROMPT

LOGGER = logging.getLogger(__name__)


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.4,
    )


def _deal_context(deal: DealInfo) -> str:
    return (
        f"Company: {deal.company_name or '(unknown)'}\n"
        f"Contact: {deal.contact_name or '(unknown)'} <{deal.contact_email or 'n/a'}>\n"
        f"Deal value: ${deal.deal_value:,.0f}\n"
        f"Stage: {deal.current_stage or '(unknown)'}\n"
        f"Days since activity: {deal.days_since_activity}\n"
    )


def _join_block(lines: list[str]) -> str:
    """Join lines into one paragraph; keep sign-off name on its own line."""
    if not lines:
        return ""
    if lines[0].lower().startswith("best,"):
        if len(lines) == 1:
            match = re.match(r"^Best,\s+(.+)$", lines[0], re.IGNORECASE)
            if match:
                return f"Best,\n{match.group(1).strip()}"
            return lines[0]
        return "\n".join(lines)
    return " ".join(lines)


def _split_cta(main: str) -> list[str]:
    """Pull a trailing call-to-action question into its own paragraph."""
    text = main.strip()
    if not text:
        return []
    if "?" not in text:
        return [text]

    comma_cta = re.search(
        r",\s*((?:can|could|would|will|are|is|do|shall|may)\s+[^,?]*\?)\s*$",
        text,
        re.IGNORECASE,
    )
    if comma_cta:
        before = text[: comma_cta.start()].strip().rstrip(",")
        question = comma_cta.group(1).strip()
        return [p for p in (before, question) if p]

    period_cta = re.search(
        r"\.\s+((?:can|could|would|will|are|is|do|shall|may)\s+"
        r"(?:you|we|there|i)\s+[^?]*\?)\s*$",
        text,
        re.IGNORECASE,
    )
    if period_cta:
        before = text[: period_cta.start() + 1].strip()
        question = period_cta.group(1).strip()
        return [p for p in (before, question) if p]

    q_end = text.rfind("?")
    start = text.rfind(". ", 0, q_end)
    if start >= 0:
        start += 2
        before = text[:start].strip()
        question = text[start : q_end + 1].strip()
        if question and len(question) <= max(40, len(text) // 2):
            return [p for p in (before, question) if p]

    return [text]


def _structure_body(body: str, sender_name: str) -> str:
    """
    Rebuild paragraph breaks when the LLM returns one long line (no blank lines).

    Target shape:
      Hi Name,

      <body paragraph(s)>

      Best,
      Sender
    """
    text = body.replace("\r\n", "\n").strip()
    signoff_name = sender_name.strip() or "Sales Team"

    signoff_match = re.search(r"\bBest,\s*(.+)$", text, re.IGNORECASE | re.DOTALL)
    if signoff_match:
        signoff_name = signoff_match.group(1).strip()
        text = text[: signoff_match.start()].strip().rstrip(",")

    greeting = ""
    greet_match = re.match(
        r"^((?:Hi|Hello|Hey|Dear)\s+[^,\n]+,)\s*",
        text,
        re.IGNORECASE,
    )
    if greet_match:
        greeting = greet_match.group(1).strip()
        text = text[greet_match.end() :].strip()

    body_parts = _split_cta(text) if text else []

    paragraphs: list[str] = []
    if greeting:
        paragraphs.append(greeting)
    paragraphs.extend(body_parts)
    paragraphs.append(f"Best,\n{signoff_name}")
    return "\n\n".join(paragraphs)


def _needs_structure(body: str) -> bool:
    """True when greeting, body, and sign-off are not separated yet."""
    stripped = body.strip()
    if re.match(
        r"^(?:Hi|Hello|Hey|Dear)\s+[^,\n]+,\s+\S",
        stripped,
        re.IGNORECASE,
    ):
        return True
    return len(re.split(r"\n\s*\n", stripped)) < 3


def _normalize_body(body: str, sender_name: str) -> str:
    """Reflow wrapped lines into paragraphs and ensure a name after Best,"""
    body = body.replace("\r\n", "\n").strip()

    # Groq often ignores blank-line instructions; fix before block splitting.
    if _needs_structure(body):
        body = _structure_body(body, sender_name)

    blocks = re.split(r"\n\s*\n", body)
    paragraphs: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        joined = _join_block(lines)
        if joined:
            paragraphs.append(joined)

    if not paragraphs:
        return body

    text = "\n\n".join(paragraphs)

    # Add sign-off only if sender name is missing entirely
    if sender_name and not re.search(re.escape(sender_name), text, re.IGNORECASE):
        text = f"{text}\n\nBest,\n{sender_name}"
    else:
        # Fix "Best, Name" on one line → two lines
        text = re.sub(
            r"Best,\s+([^\n]+)",
            r"Best,\n\1",
            text,
            count=1,
            flags=re.IGNORECASE,
        )

    return text


def _parse_email(raw: str, *, sender_name: str = "") -> dict[str, str]:
    text = raw.strip()
    subject = "Following up"
    body = text

    subject_match = re.search(r"^SUBJECT:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    body_match = re.search(r"^BODY:\s*\n?", text, re.MULTILINE | re.IGNORECASE)

    if subject_match:
        subject = subject_match.group(1).strip()
    if body_match:
        body = text[body_match.end() :].strip()
    elif subject_match:
        body = re.sub(
            r"^SUBJECT:\s*.+$",
            "",
            text,
            count=1,
            flags=re.MULTILINE | re.IGNORECASE,
        ).strip()

    body = _normalize_body(body, sender_name)
    return {"subject": subject, "body": body}


def _draft_email(deal: DealInfo, report: str, score: str) -> dict[str, str]:
    llm = _llm()
    sender = settings.sender_name.strip() or "Sales Team"
    user_content = (
        f"{_deal_context(deal)}\n"
        f"Sender name for sign-off: {sender}\n"
        f"Deal score: {score}\n"
        f"--- Research brief ---\n"
        f"{report or '(no research available)'}"
    )
    response = llm.invoke(
        [
            SystemMessage(content=WRITER_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]
    )
    return _parse_email(str(response.content), sender_name=sender)


def email_writer_node(state: AgentState) -> dict[str, Any]:
    """Draft one email (next deal without a draft yet)."""
    idx = len(state.drafted_emails)
    deals = state.stalled_deals

    if idx >= len(deals):
        LOGGER.info("Writer: no remaining deals (index=%s)", idx)
        return {}

    deal = deals[idx]
    company = deal.company_name or deal.deal_id
    report = state.research_reports.get(deal.deal_id, "")
    score = state.deal_scores.get(deal.deal_id, "warm")

    LOGGER.info("Drafting email for deal %s (%s)", deal.deal_id, company)

    drafts = dict(state.drafted_emails)
    update: dict[str, Any] = {"drafted_emails": drafts}

    try:
        email = _draft_email(deal, report, score)
        drafts[deal.deal_id] = email
        update["actions_taken"] = [f"drafted_email:{deal.deal_id}"]
        LOGGER.info("Drafted email for %s: %s", company, email["subject"])
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Email draft failed for deal %s", deal.deal_id)
        drafts[deal.deal_id] = {"subject": "", "body": ""}
        update["errors"] = [f"email_writer:{deal.deal_id}: {exc}"]

    return update
