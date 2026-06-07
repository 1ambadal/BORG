"""
generate token for google services
use: python scripts/generate_token.py
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]


def get_token():
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    creds = None

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    token_json_path = os.path.join(project_root, "token.json")
    creds_path = os.path.join(project_root, "credentials.json")

    if os.path.exists(token_json_path):
        try:
            creds = Credentials.from_authorized_user_file(token_json_path)
            print("Loaded existing credentials from token.json")
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing credentials...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Failed to refresh: {e}. Re-authenticating...")
                creds = None

        if not creds or not creds.valid:
            if not os.path.exists(creds_path):
                print(f"❌ Error: 'credentials.json' not found at {creds_path}")
                return

            print("No valid token found. Starting Google authentication flow...")
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_json_path, "w") as token:
            token.write(creds.to_json())
        print(f"✅ Success! 'token.json' generated at {token_json_path}")


if __name__ == "__main__":
    get_token()
