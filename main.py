"""CLI entry point: run the Sentinel pipeline manually."""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

load_dotenv()

from runner import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
)


if __name__ == "__main__":
    sys.exit(run_pipeline(trigger="manual"))
