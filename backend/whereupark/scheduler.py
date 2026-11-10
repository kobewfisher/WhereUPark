"""Periodic retraining. Run as its own process: `python -m whereupark schedule`.

Default: every Sunday at 03:00 campus time (lowest-traffic window). Override with
WHEREUPARK_RETRAIN_CRON (standard 5-field cron, campus time zone).
"""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import CAMPUS_TZ
from .training import retrain

DEFAULT_CRON = "0 3 * * sun"


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cron = os.environ.get("WHEREUPARK_RETRAIN_CRON", DEFAULT_CRON)
    sched = BlockingScheduler(timezone=CAMPUS_TZ)
    sched.add_job(retrain, CronTrigger.from_crontab(cron, timezone=CAMPUS_TZ),
                  id="retrain", max_instances=1, coalesce=True, misfire_grace_time=3600)
    logging.info("Retraining scheduled: '%s' (%s)", cron, CAMPUS_TZ)
    sched.start()
