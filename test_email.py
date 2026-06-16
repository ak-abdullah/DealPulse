"""Send or preview a sample email to verify formatting (no full pipeline)."""

from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

from agents.email_writer import _normalize_body
from config.settings import settings
from tools.gmail import _body_to_html, send_email

# Intentionally includes awkward line breaks — normalize + HTML should fix them.
RAW_SAMPLE = """Hi Alex,

I wanted to touch base regarding our scheduled appointment. Are we
still on track to move forward as discussed? I'm eager to proceed with
the next steps and explore how our solution can support your team's goals.

Can we schedule a quick 15-minute call this week to confirm the details?

Best,
{name}"""


def _sample_body() -> str:
    name = settings.sender_name.strip() or "Sales Team"
    body = RAW_SAMPLE.format(name=name)
    return _normalize_body(body, name)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test Sentinel email formatting (Gmail HTML + signature)."
    )
    parser.add_argument(
        "--to",
        help="Recipient email (required unless --preview-only)",
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Print plain text + save test_email_preview.html (no send)",
    )
    args = parser.parse_args()

    body = _sample_body()
    subject = "Sentinel formatting test"

    if args.preview_only:
        preview_path = "test_email_preview.html"
        html_doc = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>Email preview</title></head><body>"
            f"{_body_to_html(body)}</body></html>"
        )
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html_doc)
        print(f"HTML preview saved: {preview_path}\n")
        print("--- Plain text body ---\n")
        print(body)
        return 0

    if not args.to:
        parser.error("--to is required when not using --preview-only")

    message_id = send_email(args.to, subject, body)
    print(f"Test email sent to {args.to}")
    print(f"Gmail message id: {message_id}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main())
