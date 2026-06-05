import os, json, base64
from datetime import datetime, timezone
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


# ---- Usage counters: cost guards for the Recommendations feature -----------

def _incr_if_under(doc_ref, cap):
    """Atomically increment doc_ref's `count` if it is below `cap`. Returns True
    if incremented (was under cap), False if the cap was already reached. Runs in
    a transaction so concurrent requests can't both slip past the limit."""
    transaction = _get_db().transaction()

    @_firestore.transactional
    def _run(txn):
        snap = doc_ref.get(transaction=txn)
        count = (snap.to_dict() or {}).get('count', 0) if snap.exists else 0
        if count >= cap:
            return False
        txn.set(doc_ref, {'count': count + 1}, merge=True)
        return True

    return _run(transaction)


def consume_gemini_round(cap):
    """Count one Gemini round against the global monthly cap (keyed by UTC month).
    Returns True if under cap (and counts it), False if the cap is reached.

    Fails OPEN on Firestore errors — a transient datastore blip shouldn't take the
    feature down, and the Cloud Billing budget/alert is the hard backstop."""
    month = datetime.now(timezone.utc).strftime('%Y-%m')
    ref = _get_db().collection('usage').document('gemini_rounds_' + month)
    try:
        return _incr_if_under(ref, cap)
    except Exception:
        return True


def allow_ip_request(ip, limit):
    """Count one request from `ip` against its daily limit (keyed by UTC day).
    Returns True if under the limit (and counts it), False if exceeded. Fails
    OPEN on Firestore errors."""
    day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    safe = (ip or 'unknown').replace('/', '_').replace(':', '_').replace('.', '-')
    ref = _get_db().collection('ratelimit').document('{0}_{1}'.format(safe, day))
    try:
        return _incr_if_under(ref, limit)
    except Exception:
        return True
