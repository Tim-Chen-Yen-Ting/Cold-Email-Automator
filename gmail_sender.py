"""
Gmail API sender. Returns thread_id on success, None on failure.
Run setup_gmail.py once to generate token.json before using this.
"""

import os
import base64
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

_service_cache = None


def get_service():
    global _service_cache
    if _service_cache:
        return _service_cache

    creds_path = os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json")
    token_path = os.environ.get("GMAIL_TOKEN_PATH", "token.json")

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    _service_cache = build("gmail", "v1", credentials=creds)
    return _service_cache


def send_email(to_email: str, to_name: str, subject: str, body: str, from_email: str) -> str | None:
    """Send email. Returns thread_id on success, None on failure."""
    try:
        service = get_service()

        message = MIMEText(body, "plain")
        message["to"] = f"{to_name} <{to_email}>"
        message["from"] = from_email
        message["subject"] = subject

        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = service.users().messages().send(
            userId="me",
            body={"raw": encoded}
        ).execute()

        thread_id = result.get("threadId", "")
        print(f"[gmail] Sent → {to_email} (thread: {thread_id})")
        return thread_id

    except Exception as e:
        print(f"[gmail] Failed to send to {to_email}: {e}")
        return None
