"""
Run this ONCE to authorize Gmail + Sheets access.
You need credentials.json from Google Cloud Console first.

Steps:
1. Go to https://console.cloud.google.com/
2. Create a project → Enable Gmail API AND Google Sheets API
3. OAuth consent screen → External → Add your Gmail as test user
4. Credentials → Create OAuth 2.0 Client ID → Desktop app
5. Download JSON → save as credentials.json in this folder
6. Run: python setup_gmail.py
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("token.json", "w") as f:
    f.write(creds.to_json())

print("token.json saved. Gmail + Sheets authorized.")
