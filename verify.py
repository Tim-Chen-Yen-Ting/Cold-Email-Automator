"""
Email verification via Reoon API.
Returns: 'valid', 'risky', 'invalid', or 'unknown'
"""

import os
import requests


REOON_API_URL = "https://emailverifier.reoon.com/api/v1/verify"
ACCEPTED = {"valid", "risky"}


def verify_email(email: str) -> str:
    api_key = os.environ.get("REOON_API_KEY", "")
    if not api_key:
        print("[verify] No REOON_API_KEY set — skipping verification")
        return "unknown"

    try:
        resp = requests.get(
            REOON_API_URL,
            params={"email": email, "key": api_key, "mode": "quick"},
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "unknown").lower()
        print(f"[verify] {email} → {status}")
        return status
    except Exception as e:
        print(f"[verify] Error verifying {email}: {e}")
        return "unknown"


def is_sendable(status: str) -> bool:
    return status in ACCEPTED
