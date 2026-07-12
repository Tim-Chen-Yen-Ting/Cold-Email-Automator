"""
Core pipeline: research → verify → draft → store → send.
Called by scheduler or manually via main.py.
"""

import json

import database as db
import research
import verify
import drafter
import gmail_sender


def load_config():
    import os
    if not os.path.exists("config.json"):
        raise FileNotFoundError(
            "config.json not found. Copy config.example.json → config.json and fill in your details."
        )
    with open("config.json", encoding="utf-8") as f:
        return json.load(f)


def run_research_and_draft(config: dict, count: int = 10):
    """Research new contacts, verify emails, draft emails, store in DB."""
    campaign = config.get("campaign_label", "default")
    print(f"\n[pipeline] Researching {count} contacts (campaign: {campaign})...")
    contacts = research.research_contacts(config, count=count)
    print(f"[pipeline] Found {len(contacts)} contacts")

    drafted = 0
    for contact in contacts:
        email = (contact.email if hasattr(contact, "email") else contact.get("email", "")).strip().lower()
        name = contact.name if hasattr(contact, "name") else contact.get("name", "Unknown")
        company = contact.company if hasattr(contact, "company") else contact.get("company", "")

        if not email:
            print(f"[pipeline] Skipping {name} — no email found")
            continue

        # Blocklist check
        if db.is_blocklisted(email):
            print(f"[pipeline] Skipping {email} — blocklisted")
            continue

        # Already contacted check
        if config["limits"]["skip_if_already_contacted"] and db.already_contacted(email):
            print(f"[pipeline] Skipping {email} — already contacted")
            continue

        # Verify email (use cached result if available)
        if config["limits"].get("verify_emails", True):
            cached = db.get_verification(email)
            if cached:
                status = cached
            else:
                status = verify.verify_email(email)
                db.save_verification(email, status)

            if not verify.is_sendable(status):
                print(f"[pipeline] Skipping {email} — verification: {status}")
                continue
        else:
            print(f"[pipeline] Verification disabled — skipping check for {email}")

        # Draft email
        print(f"[pipeline] Drafting email for {name} at {company}...")
        subject, body, appeal_angle = drafter.draft_email(contact, config)

        # Store contact
        contact_id = db.upsert_contact(
            name=name,
            email=email,
            company=company,
            role=contact.role if hasattr(contact, "role") else contact.get("role", ""),
            website=contact.website if hasattr(contact, "website") else contact.get("website", ""),
            linkedin=contact.linkedin if hasattr(contact, "linkedin") else contact.get("linkedin", ""),
            source_url=contact.source_url if hasattr(contact, "source_url") else contact.get("source_url", ""),
            notes=contact.notes if hasattr(contact, "notes") else contact.get("notes", ""),
            appeal_angle=appeal_angle,
            campaign=campaign,
        )
        db.update_contact_status(email, "drafted")
        db.save_email_draft(contact_id, subject, body)
        print(f"[pipeline] Draft saved for {name} <{email}> | angle: {appeal_angle}")
        drafted += 1

    print(f"[pipeline] Done. {drafted} drafts created.")
    return drafted


def run_send(config: dict):
    """Send pending drafts up to the daily limit."""
    daily_max = config["limits"]["daily_max"]
    already_sent = db.count_sent_today()
    remaining = daily_max - already_sent

    if remaining <= 0:
        print(f"[pipeline] Daily send limit ({daily_max}) reached.")
        return 0

    per_run = min(config["scheduling"]["emails_per_run"], remaining)
    pending = db.get_pending_emails(limit=per_run)
    print(f"[pipeline] Sending {len(pending)} emails (daily remaining: {remaining})...")

    sent = 0
    from_email = config["sender"]["email"]
    for email_id, name, to_email, subject, body in pending:
        thread_id = gmail_sender.send_email(to_email, name, subject, body, from_email)
        if thread_id is not None:
            db.mark_sent(email_id, thread_id)
            sent += 1

    print(f"[pipeline] Sent {sent} emails.")
    return sent


def run_full_cycle(config: dict = None):
    """Research + draft + send in one go."""
    if config is None:
        config = load_config()
    db.init_db()
    run_research_and_draft(config, count=config["scheduling"]["emails_per_run"])
    run_send(config)
