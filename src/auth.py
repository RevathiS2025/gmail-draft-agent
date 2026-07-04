"""Google authentication: build Gmail and Drive clients from a stored
long-lived refresh token. No interactive OAuth flow at runtime.
"""

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src import config

TOKEN_URI = "https://oauth2.googleapis.com/token"


def get_credentials() -> Credentials:
    return Credentials(
        token=None,
        refresh_token=config.GOOGLE_REFRESH_TOKEN,
        token_uri=TOKEN_URI,
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
        scopes=config.GOOGLE_SCOPES,
    )


def get_gmail_client():
    return build("gmail", "v1", credentials=get_credentials())


def get_drive_client():
    return build("drive", "v3", credentials=get_credentials())
