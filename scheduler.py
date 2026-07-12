"""
Runs the cold email pipeline on a recurring schedule.
Keep this running: python scheduler.py
"""

import json
import os
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

load_dotenv()

import database as db
import pipeline
import bounce_reply
import sheets_sync


def load_config():
    with open("config.json", encoding="utf-8") as f:
        return json.load(f)


def main_job():
    config = load_config()
    print(f"\n{'='*50}")
    print("Scheduled run: research + draft + send")
    print(f"{'='*50}")
    pipeline.run_full_cycle(config)
    sheets_sync.sync(config)


def check_job():
    config = load_config()
    print(f"\n{'='*50}")
    print("Scheduled run: bounce + reply check")
    print(f"{'='*50}")
    bounce_reply.run_all()
    sheets_sync.sync(config)


if __name__ == "__main__":
    db.init_db()
    config = load_config()
    sched_cfg = config["scheduling"]

    tz = pytz.timezone(sched_cfg["timezone"])
    send_time = sched_cfg["send_time"]
    hour, minute = send_time.split(":")
    interval_hours = sched_cfg["interval_hours"]

    scheduler = BlockingScheduler(timezone=tz)

    # Main pipeline job
    if interval_hours == 24:
        main_trigger = CronTrigger(hour=int(hour), minute=int(minute), timezone=tz)
        print(f"Main pipeline: daily at {send_time} {sched_cfg['timezone']}")
    else:
        main_trigger = IntervalTrigger(hours=interval_hours, timezone=tz)
        print(f"Main pipeline: every {interval_hours} hours")

    scheduler.add_job(main_job, main_trigger, id="main_pipeline")

    # Bounce + reply check every 6 hours
    scheduler.add_job(
        check_job,
        IntervalTrigger(hours=6, timezone=tz),
        id="check_job"
    )

    print("Running first full cycle now...")
    main_job()

    print("Running initial bounce/reply check...")
    check_job()

    print("\nScheduler started. Press Ctrl+C to stop.")
    scheduler.start()
