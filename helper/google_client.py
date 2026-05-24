import base64
import json
import os

import gspread
from google.oauth2 import service_account
import google.auth

_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
]

def get_gspread_client():
    """
    Initializes and returns a gspread client using service account credentials.
    Supports local key files, base64-encoded environment variables, or default auth.
    """
    # Prefer an explicit key file (local dev)
    key_file = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if key_file and os.path.exists(key_file):
        creds = service_account.Credentials.from_service_account_file(
            key_file, scopes=_SCOPES
        )
    # GAE: metadata-server credentials can't be scoped for Workspace APIs,
    # so we require the key JSON delivered as a base64 env var.
    elif os.environ.get('GOOGLE_SA_KEY_B64'):
        info = json.loads(base64.b64decode(os.environ['GOOGLE_SA_KEY_B64']))
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=_SCOPES
        )
    else:
        creds, _ = google.auth.default(scopes=_SCOPES)
    
    return gspread.Client(auth=creds)
