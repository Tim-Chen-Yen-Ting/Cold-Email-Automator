"""
Manual control interface.

Usage:
  python main.py research     # research + draft only, no send
  python main.py send         # send pending drafts only
  python main.py run          # full cycle (research + draft + send)
  python main.py status       # show DB stats
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

import database as db
import pipeline


def status():
    db.init_db()
    with db.get_conn() as conn:
        total_contacts = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        total_drafts = conn.execute("SELECT COUNT(*) FROM emails WHERE status='draft'").fetchone()[0]
        total_sent = conn.execute("SELECT COUNT(*) FROM emails WHERE status='sent'").fetchone()[0]
        sent_today = db.count_sent_today()

    print(f"\n{'='*40}")
    print(f"  Contacts in DB:    {total_contacts}")
    print(f"  Drafts pending:    {total_drafts}")
    print(f"  Total sent:        {total_sent}")
    print(f"  Sent today:        {sent_today}")
    print(f"{'='*40}\n")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    config = pipeline.load_config()
    db.init_db()

    if cmd == "research":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else config["scheduling"]["emails_per_run"]
        pipeline.run_research_and_draft(config, count=count)

    elif cmd == "send":
        pipeline.run_send(config)

    elif cmd == "run":
        pipeline.run_full_cycle(config)

    elif cmd == "status":
        status()

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
