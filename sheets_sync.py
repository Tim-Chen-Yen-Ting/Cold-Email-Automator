"""
Syncs SQLite data to a Google Sheet.
Creates the sheet automatically on first run if sheets_id is not set in config.
"""

import json
from googleapiclient.discovery import build
import gmail_sender
import database as db


HEADERS = [
    "Name", "Email", "Company", "Role", "Website", "LinkedIn",
    "Appeal Angle", "Campaign", "Status", "Researched At",
    "Subject", "Sent At", "Bounced", "Replied",
    "Bounce Detected At", "Reply Detected At"
]


def _get_sheets_service():
    creds = gmail_sender.get_service()._http.credentials
    return build("sheets", "v4", credentials=creds)


def _create_sheet(service, title="Cold Email Tracker") -> str:
    spreadsheet = service.spreadsheets().create(body={
        "properties": {"title": title},
        "sheets": [{"properties": {"title": "Contacts"}}]
    }).execute()
    sheet_id = spreadsheet["spreadsheetId"]
    print(f"[sheets] Created new spreadsheet: {spreadsheet['spreadsheetUrl']}")
    return sheet_id


def _format_row(row: tuple) -> list:
    result = []
    for val in row:
        if val is None:
            result.append("")
        elif isinstance(val, int):
            result.append("Yes" if val == 1 else "No" if val == 0 else str(val))
        else:
            result.append(str(val))
    return result


def sync(config: dict):
    sheets_id = config.get("google_sheets", {}).get("sheets_id", "")

    service = _get_sheets_service()

    if not sheets_id:
        sheets_id = _create_sheet(service)
        # Persist to config
        config.setdefault("google_sheets", {})["sheets_id"] = sheets_id
        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)
        print(f"[sheets] Saved sheets_id to config.json: {sheets_id}")

    rows = db.get_all_for_sheets()
    values = [HEADERS] + [_format_row(row) for row in rows]

    # Clear and rewrite
    service.spreadsheets().values().clear(
        spreadsheetId=sheets_id,
        range="Contacts!A1:Z10000"
    ).execute()

    service.spreadsheets().values().update(
        spreadsheetId=sheets_id,
        range="Contacts!A1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()

    print(f"[sheets] Synced {len(rows)} rows to Google Sheets.")

    # Bold the header row
    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheets_id,
            body={"requests": [{
                "repeatCell": {
                    "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                    "fields": "userEnteredFormat.textFormat.bold"
                }
            }]}
        ).execute()
    except Exception:
        pass  # formatting is non-critical
