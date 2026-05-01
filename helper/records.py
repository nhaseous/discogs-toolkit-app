import base64, csv, json, os, re

import gspread
from google.oauth2 import service_account
import google.auth

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

SHEET_ID = '1i8mtuKXmPsCAWXLHSGDdQjhWB7cBBkJaWErSfx6TYPA'
_SCOPES   = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
]

COLLECTION_SUBFOLDERS    = {'$10-20', '$20-30', '$30-40', '$40-50', '$50-100', '$100-200', '$200+', 'Trades', 'Free'}
_COLLECTION_STOP_HEADERS = {'Spring Cleaning'}
INVENTORY_SUBFOLDERS     = {'Shop', 'Doubles', 'Generic', 'Top Shelf', 'Reserves'}
_INVENTORY_STOP_HEADERS  = {'Collection'}

_HEADER_KEYWORDS = {
    'artist', 'album', 'album title', 'cost', 'bought for', 'median', 'acquired',
    'sold for', 'sold date', 'location', 'store', 'collection', 'inventory', 'sold',
    'total', 'type', 'color', 'number', 'comment', 'comments', 'sealed', 'copies',
    'date', 'price', 'value', 'format', 'note', 'notes', 'title',
}

# ── Credentials ──────────────────────────────────────────────────────────────

def _get_client():
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

# ── Row utilities ─────────────────────────────────────────────────────────────

def _parse_price(val):
    if not val:
        return None
    v = str(val).strip()
    if v in ('---', '', '-', 'N/A', 'n/a', '0'):
        return None
    bracket = re.match(r'^\[(\d+(?:\.\d+)?)\]$', v)
    if bracket:
        return float(bracket.group(1))
    cleaned = re.sub(r'[$,]', '', v)
    try:
        return float(cleaned)
    except ValueError:
        return None


def _get(row, idx):
    try:
        v = row[idx]
        return v.strip() if isinstance(v, str) else str(v).strip()
    except (IndexError, AttributeError):
        return ''


def _is_record(row):
    artist = _get(row, 0)
    album  = _get(row, 1)
    if not artist or not album:
        return False
    if artist.lower() in _HEADER_KEYWORDS:
        return False
    return True


_DATE_RE = re.compile(r'\d{1,4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,4}')


def _is_numeric(val):
    try:
        float(re.sub(r'[$,]', '', val.strip()))
        return True
    except (ValueError, AttributeError):
        return False


def _is_sold_record(row):
    if len(row) < 6:
        return False
    first  = _get(row, 0)
    second = _get(row, 1)
    if not first or not second:
        return False
    if not _DATE_RE.search(_get(row, 4)):
        return False
    if not _get(row, 5):
        return False
    return True

# ── Row parsers (accept list-of-lists from either CSV or Sheets) ──────────────

def _parse_collection(rows):
    subfolders = []
    current    = None
    stopped    = False
    phase      = 'pre_header'   # switches to 'main' after the Artist header row
    gear_sf    = None            # active Gear subfolder, or None

    for row in rows:
        if not row:
            continue
        first = _get(row, 0)

        # ── Pre-header phase ──────────────────────────────────────────────────
        if phase == 'pre_header':
            # Gear section start — this row is its own header, so skip it
            if first == 'Gear':
                gear_sf = {'name': 'Gear', 'records': []}
                subfolders.append(gear_sf)
                continue

            # End of Gear section
            if first == 'Total' and gear_sf is not None:
                gear_sf = None
                continue

            # Main header row — switch to main parsing phase
            if first == 'Artist':
                phase = 'main'
                continue

            # Parse Gear items
            if gear_sf is not None and first:
                parts    = first.split(' ', 1)
                artist   = parts[0]
                album    = parts[1] if len(parts) > 1 else ''
                cost_raw = _get(row, 1)
                gear_sf['records'].append({
                    'artist':     artist,
                    'album':      album,
                    'cost':       cost_raw,
                    'cost_val':   _parse_price(cost_raw),
                    'median':     '',
                    'median_val': None,
                    'acquired':   '',
                    'color':      '',
                    'type':       '',
                    'number':     '',
                    'comment':    '',
                    'subfolder':  'Gear',
                })
            continue

        # ── Main phase ────────────────────────────────────────────────────────
        if first in _COLLECTION_STOP_HEADERS:
            current = None
            stopped = True
            continue

        if first in COLLECTION_SUBFOLDERS:
            current = {'name': first, 'records': []}
            subfolders.append(current)
            stopped = False
            continue

        if stopped or not _is_record(row):
            continue

        if current is None:
            current = {'name': '', 'records': []}
            subfolders.append(current)

        cost_raw   = _get(row, 2)
        median_raw = _get(row, 3)
        current['records'].append({
            'artist':     _get(row, 0),
            'album':      _get(row, 1),
            'cost':       cost_raw,
            'cost_val':   _parse_price(cost_raw),
            'median':     median_raw,
            'median_val': _parse_price(median_raw),
            'acquired':   _get(row, 4),
            'color':      _get(row, 5),
            'type':       _get(row, 6),
            'number':     _get(row, 7),
            'comment':    _get(row, 8),
            'subfolder':  current['name'],
        })

    return subfolders


def _parse_inventory(rows):
    subfolders = []
    current    = None
    stopped    = False

    for row in rows:
        if not row:
            continue
        first  = _get(row, 0)
        second = _get(row, 1)

        if not first and second in _INVENTORY_STOP_HEADERS:
            stopped = True
            continue

        if stopped:
            continue

        if not first and second in INVENTORY_SUBFOLDERS:
            current = {'name': second, 'records': []}
            subfolders.append(current)
            continue

        if not _is_record(row):
            continue

        if current is None:
            current = {'name': '', 'records': []}
            subfolders.append(current)

        cost_raw  = _get(row, 2)
        total_raw = _get(row, 3)
        d_raw     = _get(row, 6)
        listed    = bool(d_raw and d_raw.lower() not in ('', 'n', 'no', 'false', '0'))

        current['records'].append({
            'artist':    first,
            'album':     second,
            'cost':      cost_raw,
            'cost_val':  _parse_price(cost_raw),
            'total':     total_raw,
            'total_val': _parse_price(total_raw),
            'type':      _get(row, 4),
            'copies':    _get(row, 5),
            'listed':    listed,
            'comment':   _get(row, 7),
            'subfolder': current['name'],
        })

    return subfolders


def _parse_sold(rows):
    subfolders = []
    current    = None
    started    = False

    for row in rows:
        if not row:
            continue
        first = _get(row, 0)

        if not started:
            if first.lower() == 'sold':
                started = True
            continue

        if re.match(r'^\d{4}$', first):
            current = {'name': first, 'records': []}
            subfolders.append(current)
            continue

        if not _is_sold_record(row):
            continue

        if current is None:
            current = {'name': '', 'records': []}
            subfolders.append(current)

        cost_raw = _get(row, 2)
        sold_raw = _get(row, 3)
        current['records'].append({
            'artist':        _get(row, 0),
            'album':         _get(row, 1),
            'cost':          cost_raw,
            'cost_val':      _parse_price(cost_raw),
            'sold_for':      sold_raw,
            'sold_for_val':  _parse_price(sold_raw),
            'sold_date':     _get(row, 4),
            'sold_location': _get(row, 5),
        })

    return subfolders

# ── Stats ─────────────────────────────────────────────────────────────────────

def _compute_stats(collection, inventory, sold):
    col_recs  = [r for sf in collection for r in sf['records']]
    inv_recs  = [r for sf in inventory  for r in sf['records']]
    sold_recs = [r for sf in sold       for r in sf['records']]

    def _sum(recs, key):
        return sum(r[key] for r in recs if r.get(key) is not None)

    col_median_total = _sum(col_recs,  'median_val')
    col_cost_total   = _sum(col_recs,  'cost_val')
    inv_cost_total   = _sum(inv_recs,  'cost_val')
    inv_total_total  = _sum(inv_recs,  'total_val')
    sold_cost_total  = _sum(sold_recs, 'cost_val')
    sold_for_total   = _sum(sold_recs, 'sold_for_val')

    col_sf_stats = [
        {
            'name':         sf['name'],
            'count':        len(sf['records']),
            'median_total': _sum(sf['records'], 'median_val'),
            'cost_total':   _sum(sf['records'], 'cost_val'),
        }
        for sf in collection
    ]
    inv_sf_stats = [
        {
            'name':        sf['name'],
            'count':       len(sf['records']),
            'total_total': _sum(sf['records'], 'total_val'),
        }
        for sf in inventory
    ]
    sold_sf_stats = [
        {
            'name':           sf['name'],
            'count':          len(sf['records']),
            'sold_for_total': _sum(sf['records'], 'sold_for_val'),
            'cost_total':     _sum(sf['records'], 'cost_val'),
            'net':            _sum(sf['records'], 'sold_for_val') - _sum(sf['records'], 'cost_val'),
        }
        for sf in sold
    ]

    return {
        'col_count':        len(col_recs),
        'col_median_total': col_median_total,
        'col_cost_total':   col_cost_total,
        'inv_count':        len(inv_recs),
        'inv_cost_total':   inv_cost_total,
        'inv_total_total':  inv_total_total,
        'sold_count':       len(sold_recs),
        'sold_cost_total':  sold_cost_total,
        'sold_for_total':   sold_for_total,
        'total_spent':      col_cost_total + inv_total_total + sold_cost_total,
        'net':              sold_for_total - sold_cost_total,
        'col_sf_stats':     col_sf_stats,
        'inv_sf_stats':     inv_sf_stats,
        'sold_sf_stats':    sold_sf_stats,
    }

# ── Public loaders ────────────────────────────────────────────────────────────

def load_all():
    client      = _get_client()
    spreadsheet = client.open_by_key(SHEET_ID)

    col_rows  = spreadsheet.worksheet('Collection').get_all_values()
    inv_rows  = spreadsheet.worksheet('Inventory').get_all_values()
    sold_rows = spreadsheet.worksheet('Store').get_all_values()

    collection = _parse_collection(col_rows)
    inventory  = _parse_inventory(inv_rows)
    sold       = _parse_sold(sold_rows)

    return {
        'collection': collection,
        'inventory':  inventory,
        'sold':       sold,
        'stats':      _compute_stats(collection, inventory, sold),
    }


def load_all_csv():
    """CSV fallback for local verification against the source files."""
    def _read(filename):
        path = os.path.join(DATA_DIR, filename)
        try:
            with open(path, newline='', encoding='utf-8-sig') as f:
                return list(csv.reader(f))
        except FileNotFoundError:
            return []

    collection = _parse_collection(_read('collection.csv'))
    inventory  = _parse_inventory(_read('inventory.csv'))
    sold       = _parse_sold(_read('store.csv'))

    return {
        'collection': collection,
        'inventory':  inventory,
        'sold':       sold,
        'stats':      _compute_stats(collection, inventory, sold),
    }


def empty_data():
    return {'collection': [], 'inventory': [], 'sold': [], 'stats': _compute_stats([], [], [])}
