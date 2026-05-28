#!/usr/bin/env python3.11
# reauth_gmail.py
# One-time re-auth script to add gmail.compose scope to google_token.json.
# Run this ONCE from the Jarvis folder — a browser will open to authorize.
# After completing, draft_email() in search.py will work without interruption.
#
# Usage:
#   python3.11 reauth_gmail.py

import os
import json
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

JARVIS_DIR       = Path(__file__).parent
TOKEN_FILE       = JARVIS_DIR / "google_token.json"
CREDENTIALS_FILE = JARVIS_DIR / "google_credentials.json"


def main():
    if not CREDENTIALS_FILE.exists():
        print(f"[Error] {CREDENTIALS_FILE} not found.")
        return

    # Show current scopes if token exists
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE) as f:
                current = json.load(f)
            print("Current token scopes:", current.get("scopes", []))
        except Exception:
            pass

    print("\nStarting OAuth flow — a browser window will open.")
    print("Sign in with your Google account and click 'Allow'.")
    print("Requested scopes:")
    for s in SCOPES:
        print(f"  {s}")
    print()

    flow  = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    print(f"\n[OK] Token saved to {TOKEN_FILE}")
    print("Granted scopes:", creds.scopes)
    print("\nYou can now use draft_email() — run the test to verify:")
    print("  python3.11 -c \"from search import draft_email; print(draft_email('test@test.com', 'Test draft', 'Body here.'))\"")


if __name__ == "__main__":
    main()
