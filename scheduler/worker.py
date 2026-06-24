"""
Sentinel worker: manual one-shot runs or an optional built-in daily scheduler.

Manual (always available):
    python main.py
    python run_worker.py --once

External scheduler (recommended on Windows — built-in scheduler OFF):
    Task Scheduler -> python run_worker.py --once

Built-in daemon (requires explicit opt-in):
    SCHEDULER_ENABLED=true in .env
    python run_worker.py --daemon
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import settings
from runner import run_pipeline

LOGGER = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )


def _timezone():
    try:
        return ZoneInfo(settings.scheduler_timezone)
    except ZoneInfoNotFoundError:
        LOGGER.warning(
            "Unknown SCHEDULER_TIMEZONE=%r; falling back to UTC",
            settings.scheduler_timezone,
        )
        return ZoneInfo("UTC")


def _scheduled_job() -> None:
    exit_code = run_pipeline(trigger="scheduler")
    if exit_code != 0:
        LOGGER.error("Scheduled pipeline run exited with code %s", exit_code)


def run_once() -> int:
    """Run the pipeline a single time and return the process exit code."""
    return run_pipeline(trigger="manual")


def run_daemon() -> int:
    """
    Block forever and run the pipeline on a daily cron schedule.

    Requires ``SCHEDULER_ENABLED=true`` in the environment.
    """
    if not settings.scheduler_enabled:
        LOGGER.error(
            "Built-in scheduler is disabled. Set SCHEDULER_ENABLED=true in .env "
            "to use --daemon, or run `python run_worker.py --once` manually / via "
            "Windows Task Scheduler."
        )
        return 1

    tz = _timezone()
    scheduler = BlockingScheduler(timezone=tz)
    scheduler.add_job(
        _scheduled_job,
        trigger=CronTrigger(
            hour=settings.scheduler_hour,
            minute=settings.scheduler_minute,
            timezone=tz,
        ),
        id="sentinel_pipeline",
        replace_existing=True,
    )

    def _shutdown(signum: int, _frame: object) -> None:
        LOGGER.info("Received signal %s; shutting down scheduler", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    LOGGER.info(
        "Built-in scheduler enabled; daily run at %02d:%02d %s",
        settings.scheduler_hour,
        settings.scheduler_minute,
        settings.scheduler_timezone,
    )
    LOGGER.info("Press Ctrl+C to stop the scheduler (no runs while stopped)")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        LOGGER.info("Scheduler stopped")
    return 0


def main(argv: list[str] | None = None) -> int:
    _configure_logging()

    parser = argparse.ArgumentParser(
        description="Run the Sentinel pipeline once or via the built-in daily scheduler.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--once",
        action="store_true",
        help="Run the pipeline once and exit (safe for manual use and Task Scheduler)",
    )
    mode.add_argument(
        "--daemon",
        action="store_true",
        help="Run built-in daily scheduler (requires SCHEDULER_ENABLED=true)",
    )
    args = parser.parse_args(argv)

    if args.once:
        return run_once()
    return run_daemon()


if __name__ == "__main__":
    sys.exit(main())
