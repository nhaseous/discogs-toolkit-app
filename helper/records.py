import base64, csv, html as _html, json, os, re

import gspread
from google.oauth2 import service_account
import google.auth

from helper import charts
from helper.charts import PIE_COLORS as _PIE_COLORS

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


# ── Render helpers ────────────────────────────────────────────────────────────

def _fmt_money(val):
    if val is None:
        return ''
    return '${:,.2f}'.format(val)

def _fmt_cost(raw, val):
    if not raw or raw.strip() in ('', '---'):
        return '<span class="rec-free">Free</span>'
    if re.match(r'^\[\d+(?:\.\d+)?\]$', raw.strip()):
        return _html.escape('${:,.2f}'.format(val)) if val is not None else _html.escape(raw)
    if val is not None:
        return _html.escape('${:,.2f}'.format(val))
    return _html.escape(raw)


def render_records_dashboard(stats):
    def stat_card(label, value, sub='', value_class=''):
        sub_html = '<div class="rec-stat-sub">' + sub + '</div>' if sub else ''
        val_cls = 'rec-stat-value' + (' ' + value_class if value_class else '')
        return (
            '<div class="rec-stat-card">'
            '<div class="rec-stat-label">' + label + '</div>'
            '<div class="' + val_cls + '">' + value + '</div>'
            + sub_html +
            '</div>'
        )

    def sf_row(name, count, primary_val, primary_label, secondary_val=None, secondary_label=None):
        secondary = ''
        if secondary_val is not None:
            secondary = ('<td class="rec-sf-money">' + _fmt_money(secondary_val) + '</td>'
                         '<td class="rec-sf-label">' + secondary_label + '</td>')
        return (
            '<tr>'
            '<td class="rec-sf-name">' + _html.escape(name or '—') + '</td>'
            '<td class="rec-sf-count">' + str(count) + '</td>'
            '<td class="rec-sf-money">' + _fmt_money(primary_val) + '</td>'
            '<td class="rec-sf-label">' + primary_label + '</td>'
            + secondary + '</tr>'
        )

    def breakdown_section(title, tbody_html, wide=False):
        cls = 'rec-breakdown-section' + (' rec-breakdown-section--wide' if wide else '')
        return (
            '<div class="' + cls + '">'
            '<div class="rec-breakdown-title">' + title + '</div>'
            '<table class="rec-breakdown-table"><tbody>' + tbody_html + '</tbody></table>'
            '</div>'
        )

    def dash_group(tab, cards_html, breakdown_html='', active=False):
        style = '' if active else ' style="display:none;opacity:0"'
        return (
            '<div class="rec-dash-group" data-tab-group="' + tab + '"' + style + '>'
            + ('<div class="rec-stat-grid">' + cards_html + '</div>' if cards_html else '')
            + ('<div class="rec-breakdown">' + breakdown_html + '</div>' if breakdown_html else '')
            + '</div>'
        )

    col_sf_active = [s for s in stats['col_sf_stats'] if s['count']]
    col_breakdown_rows = ''.join(
        sf_row(s['name'], s['count'], s['median_total'], 'median', s['cost_total'], 'spent')
        for s in col_sf_active
    )
    col_pie_segs = [
        {'name': s['name'], 'value': s['count'], 'color': _PIE_COLORS[i % len(_PIE_COLORS)]}
        for i, s in enumerate(col_sf_active)
    ]

    inv_sf_active = [s for s in stats['inv_sf_stats'] if s['count']]
    inv_breakdown_rows = ''.join(
        sf_row(s['name'], s['count'], s['total_total'], 'spent')
        for s in inv_sf_active
    )
    inv_pie_segs = [
        {'name': s['name'], 'value': s['count'], 'color': _PIE_COLORS[i % len(_PIE_COLORS)]}
        for i, s in enumerate(inv_sf_active)
    ]

    col_inv_group = (
        '<div class="rec-dash-group" data-tab-group="col-inv">'
        + '<div class="rec-stat-grid">'
        + stat_card('Collection Value', _fmt_money(stats['col_median_total']),
                    '{0} records'.format(stats['col_count']))
        + stat_card('Collection &middot; Spent', _fmt_money(stats['col_cost_total']),
                    '{0} records'.format(stats['col_count']))
        + stat_card('Inventory &middot; Spent', _fmt_money(stats['inv_total_total']),
                    '{0} records'.format(stats['inv_count']))
        + '</div>'
        + '<div class="rec-breakdown">'
        + '<div class="rec-breakdown-pane" data-breakdown-pane="collection">'
        + ((breakdown_section('Collection', col_breakdown_rows) + charts.pie_section('Breakdown', col_pie_segs, size=130, radius=130 * 0.42, stroke='var(--bg)', path_class='')) if col_breakdown_rows else '')
        + '</div>'
        + '<div class="rec-breakdown-pane" data-breakdown-pane="inventory" style="display:none;opacity:0">'
        + ((breakdown_section('Inventory', inv_breakdown_rows) + charts.pie_section('Breakdown', inv_pie_segs, size=130, radius=130 * 0.42, stroke='var(--bg)', path_class='')) if inv_breakdown_rows else '')
        + '</div>'
        + '</div>'
        + '</div>'
    )

    net = stats['net']
    net_cls = 'rec-stat-value--pos' if net >= 0 else 'rec-stat-value--neg'
    sold_breakdown_rows = ''.join(
        (
            '<tr>'
            '<td class="rec-sf-name">' + _html.escape(s['name'] or '—') + '</td>'
            '<td class="rec-sf-count">' + str(s['count']) + '</td>'
            '<td class="rec-sf-money">' + _fmt_money(s['sold_for_total']) + '</td>'
            '<td class="rec-sf-label">made</td>'
            '<td class="rec-sf-money">' + _fmt_money(s['cost_total']) + '</td>'
            '<td class="rec-sf-label">spent</td>'
            '<td class="rec-sf-money ' + ('rec-stat-value--pos' if s['net'] >= 0 else 'rec-stat-value--neg') + '">'
            + _fmt_money(s['net']) + '</td>'
            '<td class="rec-sf-label">net</td>'
            '</tr>'
        )
        for s in stats['sold_sf_stats'] if s['count']
    )
    sold_group = dash_group(
        'sold',
        cards_html=(
            stat_card('Net Sales', _fmt_money(stats['sold_for_total']),
                      '{0} sold'.format(stats['sold_count']))
            + stat_card('Sold &middot; Gross', _fmt_money(net), value_class=net_cls)
            + stat_card('Sold &middot; Spent', _fmt_money(stats['sold_cost_total']),
                        '{0} records'.format(stats['sold_count']))
        ),
        breakdown_html=breakdown_section('Sold by Year', sold_breakdown_rows, wide=True) if sold_breakdown_rows else '',
    )

    return '<div class="rec-dashboard">' + col_inv_group + sold_group + '</div>'


def _sf_tabs_html(tab_id, sf_names):
    buttons = ''.join(
        '<button class="rec-sf-tab" data-sf="{0}">{0}</button>'.format(_html.escape(n))
        for n in sf_names
    )
    return (
        '<div class="rec-sf-tabs" id="rec-sf-tabs-' + tab_id + '">'
        '<button class="rec-sf-tab active" data-sf="__all__">All</button>'
        + buttons + '</div>'
    )


def _toolbar_html(tab_id):
    return (
        '<div class="rec-toolbar">'
        '<input type="text" class="rec-search" placeholder="Search artist or album&hellip;" '
        'id="rec-search-' + tab_id + '" autocomplete="off">'
        '<span class="rec-count" id="rec-count-' + tab_id + '"></span>'
        '</div>'
    )


def _data_attr(name, val):
    return ' data-' + name + '="' + (str(val) if val is not None else '') + '"'


def _render_table(subfolders, *, tab_id, empty_msg, columns, row_data_attrs, row_cells):
    if not subfolders:
        return '<div class="rec-empty">' + empty_msg + '</div>'

    sf_names = [sf['name'] for sf in subfolders if sf['records']]
    sf_tabs = _sf_tabs_html(tab_id, sf_names)
    colspan = str(len(columns))

    rows = ''
    idx = 0
    for sf in subfolders:
        if not sf['records']:
            continue
        sf_key = _html.escape(sf['name'])
        rows += (
            '<tr class="rec-sf-header" data-sf="' + sf_key + '">'
            '<td colspan="' + colspan + '">' + (sf_key or '—') + '</td>'
            '</tr>'
        )
        for r in sf['records']:
            rows += (
                '<tr data-sf="' + sf_key + '"'
                ' data-artist="' + _html.escape(r['artist'].lower()) + '"'
                ' data-album="' + _html.escape(r['album'].lower()) + '"'
                + row_data_attrs(r)
                + ' data-idx="' + str(idx) + '">'
                + row_cells(r) +
                '</tr>'
            )
            idx += 1

    header_cells = ''.join(
        ('<th class="sortable" data-col="' + c['sort'] + '">' + c['label'] + '</th>')
        if c.get('sort')
        else ('<th>' + c['label'] + '</th>')
        for c in columns
    )

    return (
        sf_tabs +
        _toolbar_html(tab_id) +
        '<div class="rec-table-wrap">'
        '<table class="rec-table" id="rec-table-' + tab_id + '">'
        '<thead><tr>' + header_cells + '</tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table>'
        '</div>'
    )


def render_col_table(collection):
    columns = [
        {'label': 'Artist',   'sort': 'artist'},
        {'label': 'Album',    'sort': 'album'},
        {'label': 'Cost',     'sort': 'cost'},
        {'label': 'Median',   'sort': 'median'},
        {'label': 'Acquired', 'sort': 'acquired'},
        {'label': 'Color'},
        {'label': 'Type'},
        {'label': '#'},
        {'label': 'Note'},
    ]

    def row_attrs(r):
        return (
            _data_attr('cost',     r['cost_val'])
            + _data_attr('median', r['median_val'])
            + ' data-acquired="' + _html.escape(r['acquired']) + '"'
        )

    def row_cells(r):
        return (
            '<td>' + _html.escape(r['artist']) + '</td>'
            '<td>' + _html.escape(r['album']) + '</td>'
            '<td>' + _fmt_cost(r['cost'], r['cost_val']) + '</td>'
            '<td>' + _fmt_cost(r['median'], r['median_val']) + '</td>'
            '<td>' + _html.escape(r['acquired']) + '</td>'
            '<td>' + _html.escape(r['color']) + '</td>'
            '<td>' + _html.escape(r['type']) + '</td>'
            '<td>' + _html.escape(r['number']) + '</td>'
            '<td class="rec-comment">' + _html.escape(r['comment']) + '</td>'
        )

    return _render_table(collection, tab_id='collection',
                         empty_msg='No collection data found.',
                         columns=columns, row_data_attrs=row_attrs, row_cells=row_cells)


def render_inv_table(inventory):
    columns = [
        {'label': 'Artist', 'sort': 'artist'},
        {'label': 'Album',  'sort': 'album'},
        {'label': 'Cost',   'sort': 'cost'},
        {'label': 'Total',  'sort': 'total'},
        {'label': 'Type'},
        {'label': 'Copies'},
        {'label': 'Listed'},
        {'label': 'Note'},
    ]

    def row_attrs(r):
        return _data_attr('cost', r['cost_val']) + _data_attr('total', r['total_val'])

    def row_cells(r):
        copies_raw = r['copies'].strip()
        if copies_raw.lower() == 'sealed':
            copies_disp = '<span class="rec-badge rec-badge--sealed">Sealed</span>'
        elif copies_raw:
            try:
                copies_disp = '&times;{0}'.format(int(copies_raw))
            except ValueError:
                copies_disp = _html.escape(copies_raw)
        else:
            copies_disp = ''
        listed_badge = '<span class="rec-badge rec-badge--listed">Listed</span>' if r['listed'] else ''
        return (
            '<td>' + _html.escape(r['artist']) + '</td>'
            '<td>' + _html.escape(r['album']) + '</td>'
            '<td>' + _fmt_cost(r['cost'], r['cost_val']) + '</td>'
            '<td>' + _fmt_cost(r['total'], r['total_val']) + '</td>'
            '<td>' + _html.escape(r['type']) + '</td>'
            '<td>' + copies_disp + '</td>'
            '<td>' + listed_badge + '</td>'
            '<td class="rec-comment">' + _html.escape(r['comment']) + '</td>'
        )

    return _render_table(inventory, tab_id='inventory',
                         empty_msg='No inventory data found.',
                         columns=columns, row_data_attrs=row_attrs, row_cells=row_cells)


def render_sold_table(sold):
    columns = [
        {'label': 'Artist',     'sort': 'artist'},
        {'label': 'Album',      'sort': 'album'},
        {'label': 'Bought For', 'sort': 'cost'},
        {'label': 'Sold For',   'sort': 'sold-for'},
        {'label': 'Profit',     'sort': 'sold-for'},
        {'label': 'Date',       'sort': 'date'},
        {'label': 'Location'},
    ]

    def row_attrs(r):
        return (
            _data_attr('cost',       r['cost_val'])
            + _data_attr('sold-for', r['sold_for_val'])
            + ' data-date="' + _html.escape(r['sold_date']) + '"'
        )

    def row_cells(r):
        if r['sold_for_val'] is not None and r['cost_val'] is not None:
            profit = r['sold_for_val'] - r['cost_val']
            profit_class = 'rec-profit--pos' if profit >= 0 else 'rec-profit--neg'
            profit_html = _fmt_money(profit)
        else:
            profit_class = ''
            profit_html = ''
        return (
            '<td>' + _html.escape(r['artist']) + '</td>'
            '<td>' + _html.escape(r['album']) + '</td>'
            '<td>' + _fmt_cost(r['cost'], r['cost_val']) + '</td>'
            '<td>' + _fmt_cost(r['sold_for'], r['sold_for_val']) + '</td>'
            '<td class="' + profit_class + '">' + profit_html + '</td>'
            '<td>' + _html.escape(r['sold_date']) + '</td>'
            '<td>' + _html.escape(r['sold_location']) + '</td>'
        )

    return _render_table(sold, tab_id='sold',
                         empty_msg='No sold records found.',
                         columns=columns, row_data_attrs=row_attrs, row_cells=row_cells)
