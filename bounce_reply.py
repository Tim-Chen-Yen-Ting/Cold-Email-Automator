"""
Polls Gmail inbox to detect:
  - Bounces: emails from mailer-daemon / postmaster matching sent addresses
  - Replies: new messages in threads of sent emails
"""

import re
import database as db
import gmail_sender


def _get_service():
    return gmail_sender.get_service()


def _extract_bounced_address(snippet: str, body: str) -> str | None:
    """Try to extract the failed delivery address from a bounce email."""
    combined = snippet + " " + body
    patterns = [
        r"delivery to\s+([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\s+failed",
        r"failed to deliver.*?to\s+([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
        r"<([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})>",
        r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return None


def check_bounces():
    """Search inbox for bounce messages and mark affected emails in DB."""
    service = _get_service()
    print("[bounce] Checking for bounce notifications...")

    try:
        results = service.users().messages().list(
            userId="me",
            q="from:(mailer-daemon OR postmaster) subject:(delivery OR failed OR undeliverable)",
            maxResults=50
        ).execute()
    except Exception as e:
        print(f"[bounce] Gmail search error: {e}")
        return

    messages = results.get("messages", [])
    if not messages:
        print("[bounce] No bounce messages found.")
        return

    sent_threads = db.get_sent_threads()
    # Map email → email_id for quick lookup
    email_to_id = {row[1].lower(): row[0] for row in sent_threads}

    for msg_meta in messages:
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_meta["id"], format="full"
            ).execute()

            snippet = msg.get("snippet", "")
            # Extract plain text body
            body = ""
            payload = msg.get("payload", {})
            if payload.get("body", {}).get("data"):
                import base64
                body = base64.urlsafe_b64decode(payload["body"]["data"]).decode(errors="ignore")

            bounced_addr = _extract_bounced_address(snippet, body)
            if bounced_addr and bounced_addr in email_to_id:
                email_id = email_to_id[bounced_addr]
                db.mark_bounced(email_id)
                print(f"[bounce] Marked bounced: {bounced_addr}")

        except Exception as e:
            print(f"[bounce] Error processing message: {e}")


def check_replies():
    """For each sent thread, check if a reply exists that isn't from us."""
    service = _get_service()
    print("[reply] Checking for replies...")

    sent_threads = db.get_sent_threads()
    if not sent_threads:
        print("[reply] No threads to check.")
        return

    # Get our own email address to filter out self-messages
    try:
        profile = service.users().getProfile(userId="me").execute()
        my_email = profile.get("emailAddress", "").lower()
    except Exception:
        my_email = ""

    for email_id, contact_email, thread_id in sent_threads:
        if not thread_id:
            continue
        try:
            thread = service.users().threads().get(
                userId="me", id=thread_id, format="metadata",
                metadataHeaders=["From"]
            ).execute()

            messages = thread.get("messages", [])
            # First message is our sent email; any additional message is a reply
            if len(messages) <= 1:
                continue

            for msg in messages[1:]:
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                from_addr = headers.get("From", "").lower()
                if my_email not in from_addr:
                    db.mark_replied(email_id)
                    print(f"[reply] Reply detected from {contact_email}")
                    break

        except Exception as e:
            print(f"[reply] Error checking thread {thread_id}: {e}")


def run_all():
    check_bounces()
    check_replies()
