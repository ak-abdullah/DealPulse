"""Entry point for scheduled or one-shot pipeline runs."""

from __future__ import annotations

import sys

from scheduler.worker import main

if __name__ == "__main__":
    sys.exit(main())
