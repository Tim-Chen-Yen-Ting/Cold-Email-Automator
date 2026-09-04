"""
Gmail API sender. Returns thread_id on success, None on failure.
Run setup_gmail.py once to generate token.json before using this.
"""

import os
import base64
import httplib2
import socks
from urllib.parse import urlparse
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

_service_cache = None
_verified_account = None


def _authorized_http(creds):
    """httplib2 (unlike requests/httpx) doesn't read the Windows system proxy automatically —
    build it explicitly so Gmail/Sheets calls route through a local proxy (e.g. Hiddify) when
    one is configured. Uses a dedicated GOOGLE_API_PROXY var rather than the generic HTTP_PROXY/
    HTTPS_PROXY names, since those are also picked up by httpx (used for OpenAI calls) and would
    reroute unrelated traffic through the same proxy."""
    proxy_url = os.environ.get("GOOGLE_API_PROXY")
    http = None
    if proxy_url:
        parsed = urlparse(proxy_url)
        proxy_info = httplib2.ProxyInfo(
            proxy_type=socks.PROXY_TYPE_HTTP,
            proxy_host=parsed.hostname,
            proxy_port=parsed.port,
        )
        http = httplib2.Http(proxy_info=proxy_info)
    else:
        http = httplib2.Http()
    return AuthorizedHttp(creds, http=http)


def get_service(expected_email: str = None):
    global _service_cache, _verified_account
    if not _service_cache:
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

        _service_cache = build("gmail", "v1", http=_authorized_http(creds))

    # Gmail sends as whichever account the token belongs to, regardless of the
    # message's From header — verify it matches config once per process so a stale
    # or wrong-account token fails loudly instead of silently mis-sending.
    if expected_email and _verified_account != expected_email:
        profile = _service_cache.users().getProfile(userId="me").execute()
        actual = profile["emailAddress"]
        if actual.lower() != expected_email.lower():
            raise RuntimeError(
                f"Gmail token.json is authenticated as {actual}, but config.json sender.email "
                f"is {expected_email}. Re-run setup_gmail.py signed into {expected_email} "
                f"(use an incognito window to avoid the wrong account being picked)."
            )
        _verified_account = actual

    return _service_cache


def send_email(to_email: str, to_name: str, subject: str, body: str, from_email: str) -> str | None:
    """Send email. Returns thread_id on success, None on failure."""
    try:
        service = get_service(expected_email=from_email)

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
