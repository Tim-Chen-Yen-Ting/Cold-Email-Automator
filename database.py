import sqlite3
from datetime import datetime

DB_PATH = "cold_email.db"


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT UNIQUE,
                company TEXT,
                role TEXT,
                website TEXT,
                linkedin TEXT,
                source_url TEXT,
                notes TEXT,
                appeal_angle TEXT,
                campaign TEXT,
                status TEXT DEFAULT 'researched',
                researched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER REFERENCES contacts(id),
                subject TEXT,
                body TEXT,
                thread_id TEXT,
                status TEXT DEFAULT 'draft',
                bounced INTEGER DEFAULT 0,
                replied INTEGER DEFAULT 0,
                bounce_detected_at TEXT,
                reply_detected_at TEXT,
                sent_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS verification (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                result TEXT,
                checked_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS blocklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                reason TEXT,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Migrate existing DBs that predate new columns
        _migrate(conn)


def _migrate(conn):
    existing = {row[1] for row in conn.execute("PRAGMA table_info(contacts)")}
    new_contact_cols = {
        "source_url": "TEXT",
        "appeal_angle": "TEXT",
        "campaign": "TEXT",
        "researched_at": "TEXT",
    }
    for col, typ in new_contact_cols.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE contacts ADD COLUMN {col} {typ}")

    existing_emails = {row[1] for row in conn.execute("PRAGMA table_info(emails)")}
    new_email_cols = {
        "thread_id": "TEXT",
        "bounced": "INTEGER DEFAULT 0",
        "replied": "INTEGER DEFAULT 0",
        "bounce_detected_at": "TEXT",
        "reply_detected_at": "TEXT",
    }
    for col, typ in new_email_cols.items():
        if col not in existing_emails:
            conn.execute(f"ALTER TABLE emails ADD COLUMN {col} {typ}")


def upsert_contact(name, email, company, role="", website="", linkedin="",
                   source_url="", notes="", appeal_angle="", campaign=""):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO contacts (name, email, company, role, website, linkedin,
                                  source_url, notes, appeal_angle, campaign, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'researched')
            ON CONFLICT(email) DO UPDATE SET
                name=excluded.name,
                company=excluded.company,
                role=excluded.role,
                notes=excluded.notes,
                appeal_angle=excluded.appeal_angle,
                campaign=excluded.campaign
        """, (name, email, company, role, website, linkedin,
              source_url, notes, appeal_angle, campaign))
        return conn.execute("SELECT id FROM contacts WHERE email=?", (email,)).fetchone()[0]


def update_contact_status(email, status):
    with get_conn() as conn:
        conn.execute("UPDATE contacts SET status=? WHERE email=?", (status, email))


def save_email_draft(contact_id, subject, body):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO emails (contact_id, subject, body) VALUES (?, ?, ?)",
            (contact_id, subject, body)
        )


def get_pending_emails(limit=10):
    with get_conn() as conn:
        return conn.execute("""
            SELECT e.id, c.name, c.email, e.subject, e.body
            FROM emails e
            JOIN contacts c ON c.id = e.contact_id
            WHERE e.status = 'draft'
            ORDER BY e.created_at ASC
            LIMIT ?
        """, (limit,)).fetchall()


def mark_sent(email_id, thread_id=""):
    with get_conn() as conn:
        conn.execute(
            "UPDATE emails SET status='sent', sent_at=?, thread_id=? WHERE id=?",
            (datetime.utcnow().isoformat(), thread_id, email_id)
        )
        # Update contact status
        row = conn.execute("SELECT contact_id FROM emails WHERE id=?", (email_id,)).fetchone()
        if row:
            conn.execute("UPDATE contacts SET status='sent' WHERE id=?", (row[0],))


def get_sent_threads():
    """Return (email_id, contact_email, thread_id) for all sent, non-bounced, non-replied emails."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT e.id, c.email, e.thread_id
            FROM emails e
            JOIN contacts c ON c.id = e.contact_id
            WHERE e.status = 'sent'
              AND e.bounced = 0
              AND e.replied = 0
              AND e.thread_id IS NOT NULL
              AND e.thread_id != ''
        """).fetchall()


def mark_bounced(email_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE emails SET bounced=1, bounce_detected_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), email_id)
        )
        row = conn.execute("SELECT contact_id FROM emails WHERE id=?", (email_id,)).fetchone()
        if row:
            conn.execute("UPDATE contacts SET status='bounced' WHERE id=?", (row[0],))


def mark_replied(email_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE emails SET replied=1, reply_detected_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), email_id)
        )
        row = conn.execute("SELECT contact_id FROM emails WHERE id=?", (email_id,)).fetchone()
        if row:
            conn.execute("UPDATE contacts SET status='replied' WHERE id=?", (row[0],))


def save_verification(email, result):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO verification (email, result)
            VALUES (?, ?)
            ON CONFLICT(email) DO UPDATE SET result=excluded.result, checked_at=CURRENT_TIMESTAMP
        """, (email, result))


def get_verification(email):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT result FROM verification WHERE email=?", (email,)
        ).fetchone()
        return row[0] if row else None


def is_blocklisted(email):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM blocklist WHERE email=?", (email.lower(),)
        ).fetchone()
        return row is not None


def add_to_blocklist(email, reason="unsubscribed"):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO blocklist (email, reason) VALUES (?, ?)
        """, (email.lower(), reason))


def get_researched_companies(campaign=None, limit=100):
    """Most recently researched companies, used to steer the LLM away from re-searching them
    and to hard-filter any duplicates it returns anyway."""
    with get_conn() as conn:
        if campaign:
            rows = conn.execute(
                """SELECT DISTINCT company FROM contacts
                   WHERE campaign=? AND company != ''
                   ORDER BY researched_at DESC LIMIT ?""",
                (campaign, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT DISTINCT company FROM contacts
                   WHERE company != ''
                   ORDER BY researched_at DESC LIMIT ?""",
                (limit,)
            ).fetchall()
        return [r[0] for r in rows]


def already_contacted(email):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT e.id FROM emails e
               JOIN contacts c ON c.id=e.contact_id
               WHERE c.email=? AND e.status='sent'""",
            (email,)
        ).fetchone()
        return row is not None


def count_sent_today():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM emails WHERE status='sent' AND date(sent_at)=date('now')"
        ).fetchone()
        return row[0]


def get_all_for_sheets():
    """Return all data needed for Google Sheets sync."""
    with get_conn() as conn:
        contacts = conn.execute("""
            SELECT c.name, c.email, c.company, c.role, c.website, c.linkedin,
                   c.appeal_angle, c.campaign, c.status, c.researched_at,
                   e.subject, e.sent_at, e.bounced, e.replied,
                   e.bounce_detected_at, e.reply_detected_at
            FROM contacts c
            LEFT JOIN emails e ON e.contact_id = c.id
            ORDER BY c.researched_at DESC
        """).fetchall()
        return contacts
