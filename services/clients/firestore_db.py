import os, json, base64
from google.cloud import firestore as _firestore
from google.oauth2 import service_account as _sa

_SCOPES = ['https://www.googleapis.com/auth/datastore',
           'https://www.googleapis.com/auth/cloud-platform']

_db = None

def _get_db():
    global _db
    if _db is None:
        creds = None
        key_file = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if key_file and os.path.exists(key_file):
            creds = _sa.Credentials.from_service_account_file(key_file, scopes=_SCOPES)
        elif os.environ.get('GOOGLE_SA_KEY_B64'):
            info = json.loads(base64.b64decode(os.environ['GOOGLE_SA_KEY_B64']))
            creds = _sa.Credentials.from_service_account_info(info, scopes=_SCOPES)
        # On GAE without either env var, falls back to Application Default Credentials
        _db = _firestore.Client(project='discogs-toolkit', credentials=creds)
    return _db

def get_watchlist(username):
    doc = _get_db().collection('users').document(username).get()
    if doc.exists:
        return [str(rid) for rid in (doc.to_dict().get('watchlist') or [])]
    return []

def save_watchlist(username, release_ids):
    _get_db().collection('users').document(username).set(
        {'watchlist': release_ids},
        merge=True
    )
