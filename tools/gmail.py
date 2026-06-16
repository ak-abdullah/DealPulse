"""Gmail API: OAuth send for pipeline follow-up emails."""

from __future__ import annotations

import base64
import html
import logging
import os
import re
from email.message import EmailMessage
from email.policy import EmailPolicy
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from agents.email_writer import _normalize_body
from config.settings import settings

LOGGER = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
# Avoid folding plain-text paragraphs at 78 chars (RFC default).
_SEND_POLICY = EmailPolicy(max_line_length=998)


class GmailIntegrationError(RuntimeError):
    """Raised when Gmail send fails."""


def _use_mock() -> bool:
    return os.getenv("GMAIL_USE_MOCK", "").lower() in ("1", "true", "yes")


def _credentials() -> Credentials:
    creds_path = Path(settings.gmail_credentials_path)
    token_path = Path(settings.gmail_token_path)

    if not creds_path.is_file():
        raise GmailIntegrationError(
            f"Gmail credentials not found at {creds_path}. "
            "Download OAuth credentials.json from Google Cloud Console."
        )

    creds: Credentials | None = None
    if token_path.is_file():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def _paragraphs(body: str) -> list[str]:
    blocks = re.split(r"\n\s*\n", body.strip())
    paras: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if lines[0].lower().startswith("best,"):
            if len(lines) == 1:
                match = re.match(r"^Best,\s+(.+)$", lines[0], re.IGNORECASE)
                paras.append(
                    f"Best,\n{match.group(1).strip()}" if match else lines[0]
                )
            else:
                paras.append("\n".join(lines))
        else:
            paras.append(" ".join(lines))
    return paras or [body.strip()]


def _body_to_html(body: str) -> str:
    """Table-based HTML for Gmail (div/CSS max-width is often stripped or ignored)."""
    rows = []
    for para in _paragraphs(body):
        inner = html.escape(para).replace("\n", "<br>")
        rows.append(
            "<tr><td style=\"padding:0 0 16px 0;font-family:Arial,Helvetica,sans-serif;"
            "font-size:15px;line-height:1.6;color:#222222;width:100%;"
            "word-wrap:break-word;\">"
            f"{inner}</td></tr>"
        )
    content = "".join(rows)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#ffffff;width:100%;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="border-collapse:collapse;width:100%;background-color:#ffffff;">
    <tr>
      <td align="left" style="padding:0;width:100%;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
               style="border-collapse:collapse;width:100%;">
          {content}
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_email(
    to_email: str,
    subject: str,
    body: str,
    *,
    from_email: str | None = None,
    from_name: str | None = None,
) -> str:
    """
    Send a multipart email (plain + HTML) via Gmail API.

    Plain text keeps paragraph breaks when Gmail strips HTML (e.g. in Spam).
    HTML is the preferred part in the normal inbox view.

    Set ``GMAIL_USE_MOCK=true`` to log instead of sending (local dev).

    Returns Gmail message id (or ``mock-message-id`` in mock mode).
    """
    to_email = to_email.strip()
    if not to_email:
        raise GmailIntegrationError("Recipient email is required")

    subject = subject.strip() or "Following up"
    body = body.strip()
    if not body:
        raise GmailIntegrationError("Email body is required")

    if _use_mock():
        LOGGER.info(
            "GMAIL_USE_MOCK enabled; would send email to=%s subject=%r",
            to_email,
            subject,
        )
        return "mock-message-id"

    sender = (from_email or settings.sender_email).strip()
    if not sender:
        raise GmailIntegrationError("SENDER_EMAIL is not configured")

    display_name = (from_name or settings.sender_name).strip()
    from_header = f"{display_name} <{sender}>" if display_name else sender

    body = _normalize_body(body, display_name or "Sales Team")
    plain = body
    html_doc = _body_to_html(body)

    message = EmailMessage(policy=_SEND_POLICY)
    message["To"] = to_email
    message["From"] = from_header
    message["Subject"] = subject
    message["Reply-To"] = sender
    # Plain first, HTML last — clients prefer the richest alternative (HTML).
    message.set_content(plain, subtype="plain", charset="utf-8")
    message.add_alternative(html_doc, subtype="html")

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    service = build("gmail", "v1", credentials=_credentials(), cache_discovery=False)

    try:
        sent = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
    except HttpError as exc:
        raise GmailIntegrationError("Gmail send failed") from exc

    message_id = str(sent.get("id", ""))
    LOGGER.info("Sent email to %s (gmail_id=%s)", to_email, message_id)
    return message_id
