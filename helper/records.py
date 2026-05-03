import base64, csv, html as _html, json, math as _math, os, re

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

_PIE_COLORS = [
    '#c47a50',  # rust
    '#708a50',  # olive
    '#5a7898',  # slate blue
    '#b89858',  # tan/gold
    '#886888',  # muted purple
    '#508888',  # teal
    '#c4a040',  # amber
    '#6a8a70',  # sage
]


def _pie_svg(segments, size=130):
    total = sum(s['value'] for s in segments)
    if not segments or total == 0:
        return ''
    cx = cy = size / 2
    r = size * 0.42
    paths = []
    angle = -_math.pi / 2
    for seg in segments:
        if seg['value'] <= 0:
            continue
        sweep = 2 * _math.pi * seg['value'] / total
        end_angle = angle + sweep
        x1 = cx + r * _math.cos(angle)
        y1 = cy + r * _math.sin(angle)
        x2 = cx + r * _math.cos(end_angle)
        y2 = cy + r * _math.sin(end_angle)
        large_arc = 1 if sweep > _math.pi else 0
        d = 'M {:.2f} {:.2f} L {:.2f} {:.2f} A {:.2f} {:.2f} 0 {} 1 {:.2f} {:.2f} Z'.format(
            cx, cy, x1, y1, r, r, large_arc, x2, y2)
        paths.append('<path d="{}" fill="{}" stroke="var(--bg)" stroke-width="2"/>'.format(
            d, seg['color']))
        angle = end_angle
    return ('<svg viewBox="0 0 {0} {0}" xmlns="http://www.w3.org/2000/svg"'
            ' class="rec-pie-svg">{1}</svg>'.format(size, ''.join(paths)))


def _pie_section(title, segments):
    total = sum(s['value'] for s in segments)
    if not segments or total == 0:
        return ''
    legend_items = ''.join(
        '<div class="rec-pie-legend-item">'
        '<span class="rec-pie-dot" style="background:{color}"></span>'
        '<span class="rec-pie-name">{name}</span>'
        '<span class="rec-pie-pct">{pct:.0f}%</span>'
        '</div>'.format(
            color=seg['color'],
            name=_html.escape(seg['name'] or '—'),
            pct=seg['value'] / total * 100,
        )
        for seg in segments if seg['value'] > 0
    )
    return (
        '<div class="rec-breakdown-section">'
        '<div class="rec-breakdown-title">' + title + '</div>'
        '<div class="rec-pie-wrap">'
        + _pie_svg(segments) +
        '<div class="rec-pie-legend">' + legend_items + '</div>'
        '</div>'
        '</div>'
    )


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
        + ((breakdown_section('Collection', col_breakdown_rows) + _pie_section('Breakdown', col_pie_segs)) if col_breakdown_rows else '')
        + '</div>'
        + '<div class="rec-breakdown-pane" data-breakdown-pane="inventory" style="display:none;opacity:0">'
        + ((breakdown_section('Inventory', inv_breakdown_rows) + _pie_section('Breakdown', inv_pie_segs)) if inv_breakdown_rows else '')
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


def render_col_table(collection):
    if not collection:
        return '<div class="rec-empty">No collection data found.</div>'

    sf_names = [sf['name'] for sf in collection if sf['records']]
    sf_tabs = (
        '<div class="rec-sf-tabs" id="rec-sf-tabs-collection">'
        '<button class="rec-sf-tab active" data-sf="__all__">All</button>'
        + ''.join('<button class="rec-sf-tab" data-sf="{0}">{0}</button>'.format(_html.escape(n)) for n in sf_names)
        + '</div>'
    )

    rows = ''
    idx = 0
    for sf in collection:
        if not sf['records']:
            continue
        sf_key = _html.escape(sf['name'])
        rows += (
            '<tr class="rec-sf-header" data-sf="{0}">'
            '<td colspan="9">{1}</td>'
            '</tr>'
        ).format(sf_key, sf_key or '—')
        for r in sf['records']:
            rows += (
                '<tr data-sf="{sf}" data-artist="{artist}" data-album="{album}"'
                ' data-cost="{cost_v}" data-median="{med_v}" data-acquired="{acquired_v}" data-idx="{idx}">'
                '<td>{artist_d}</td>'
                '<td>{album_d}</td>'
                '<td>{cost_d}</td>'
                '<td>{median_d}</td>'
                '<td>{acquired}</td>'
                '<td>{color}</td>'
                '<td>{type_}</td>'
                '<td>{number}</td>'
                '<td class="rec-comment">{comment}</td>'
                '</tr>'
            ).format(
                sf=sf_key,
                artist=_html.escape(r['artist'].lower()),
                album=_html.escape(r['album'].lower()),
                cost_v=r['cost_val'] if r['cost_val'] is not None else '',
                med_v=r['median_val'] if r['median_val'] is not None else '',
                acquired_v=_html.escape(r['acquired']),
                idx=idx,
                artist_d=_html.escape(r['artist']),
                album_d=_html.escape(r['album']),
                cost_d=_fmt_cost(r['cost'], r['cost_val']),
                median_d=_fmt_cost(r['median'], r['median_val']),
                acquired=_html.escape(r['acquired']),
                color=_html.escape(r['color']),
                type_=_html.escape(r['type']),
                number=_html.escape(r['number']),
                comment=_html.escape(r['comment']),
            )
            idx += 1

    table = (
        '<div class="rec-toolbar">'
        '<input type="text" class="rec-search" placeholder="Search artist or album&hellip;" '
        'id="rec-search-collection" autocomplete="off">'
        '<span class="rec-count" id="rec-count-collection"></span>'
        '</div>'
        '<div class="rec-table-wrap">'
        '<table class="rec-table" id="rec-table-collection">'
        '<thead><tr>'
        '<th class="sortable" data-col="artist">Artist</th>'
        '<th class="sortable" data-col="album">Album</th>'
        '<th class="sortable" data-col="cost">Cost</th>'
        '<th class="sortable" data-col="median">Median</th>'
        '<th class="sortable" data-col="acquired">Acquired</th>'
        '<th>Color</th>'
        '<th>Type</th>'
        '<th>#</th>'
        '<th>Note</th>'
        '</tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table>'
        '</div>'
    )
    return sf_tabs + table


def render_inv_table(inventory):
    if not inventory:
        return '<div class="rec-empty">No inventory data found.</div>'

    sf_names = [sf['name'] for sf in inventory if sf['records']]
    sf_tabs = (
        '<div class="rec-sf-tabs" id="rec-sf-tabs-inventory">'
        '<button class="rec-sf-tab active" data-sf="__all__">All</button>'
        + ''.join('<button class="rec-sf-tab" data-sf="{0}">{0}</button>'.format(_html.escape(n)) for n in sf_names)
        + '</div>'
    )

    rows = ''
    idx = 0
    for sf in inventory:
        if not sf['records']:
            continue
        sf_key = _html.escape(sf['name'])
        rows += (
            '<tr class="rec-sf-header" data-sf="{0}">'
            '<td colspan="8">{1}</td>'
            '</tr>'
        ).format(sf_key, sf_key or '—')
        for r in sf['records']:
            listed_badge = '<span class="rec-badge rec-badge--listed">Listed</span>' if r['listed'] else ''
            copies_raw = r['copies'].strip()
            if copies_raw.lower() == 'sealed':
                copies_disp = '<span class="rec-badge rec-badge--sealed">Sealed</span>'
            elif copies_raw:
                try:
                    n = int(copies_raw)
                    copies_disp = '&times;{0}'.format(n)
                except ValueError:
                    copies_disp = _html.escape(copies_raw)
            else:
                copies_disp = ''

            rows += (
                '<tr data-sf="{sf}" data-artist="{artist}" data-album="{album}"'
                ' data-cost="{cost_v}" data-total="{total_v}" data-idx="{idx}">'
                '<td>{artist_d}</td>'
                '<td>{album_d}</td>'
                '<td>{cost_d}</td>'
                '<td>{total_d}</td>'
                '<td>{type_}</td>'
                '<td>{copies}</td>'
                '<td>{listed}</td>'
                '<td class="rec-comment">{comment}</td>'
                '</tr>'
            ).format(
                sf=sf_key,
                artist=_html.escape(r['artist'].lower()),
                album=_html.escape(r['album'].lower()),
                cost_v=r['cost_val'] if r['cost_val'] is not None else '',
                total_v=r['total_val'] if r['total_val'] is not None else '',
                idx=idx,
                artist_d=_html.escape(r['artist']),
                album_d=_html.escape(r['album']),
                cost_d=_fmt_cost(r['cost'], r['cost_val']),
                total_d=_fmt_cost(r['total'], r['total_val']),
                type_=_html.escape(r['type']),
                copies=copies_disp,
                listed=listed_badge,
                comment=_html.escape(r['comment']),
            )
            idx += 1

    table = (
        '<div class="rec-toolbar">'
        '<input type="text" class="rec-search" placeholder="Search artist or album&hellip;" '
        'id="rec-search-inventory" autocomplete="off">'
        '<span class="rec-count" id="rec-count-inventory"></span>'
        '</div>'
        '<div class="rec-table-wrap">'
        '<table class="rec-table" id="rec-table-inventory">'
        '<thead><tr>'
        '<th class="sortable" data-col="artist">Artist</th>'
        '<th class="sortable" data-col="album">Album</th>'
        '<th class="sortable" data-col="cost">Cost</th>'
        '<th class="sortable" data-col="total">Total</th>'
        '<th>Type</th>'
        '<th>Copies</th>'
        '<th>Listed</th>'
        '<th>Note</th>'
        '</tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table>'
        '</div>'
    )
    return sf_tabs + table


def render_sold_table(sold):
    if not sold:
        return '<div class="rec-empty">No sold records found.</div>'

    sf_names = [sf['name'] for sf in sold if sf['records']]
    sf_tabs = (
        '<div class="rec-sf-tabs" id="rec-sf-tabs-sold">'
        '<button class="rec-sf-tab active" data-sf="__all__">All</button>'
        + ''.join('<button class="rec-sf-tab" data-sf="{0}">{0}</button>'.format(_html.escape(n)) for n in sf_names)
        + '</div>'
    )

    rows = ''
    idx = 0
    for sf in sold:
        if not sf['records']:
            continue
        sf_key = _html.escape(sf['name'])
        rows += (
            '<tr class="rec-sf-header" data-sf="{0}">'
            '<td colspan="7">{1}</td>'
            '</tr>'
        ).format(sf_key, sf_key or '—')
        for r in sf['records']:
            profit = None
            if r['sold_for_val'] is not None and r['cost_val'] is not None:
                profit = r['sold_for_val'] - r['cost_val']
            profit_class = 'rec-profit--pos' if (profit is not None and profit >= 0) else ('rec-profit--neg' if profit is not None else '')
            rows += (
                '<tr data-sf="{sf}" data-artist="{artist}" data-album="{album}"'
                ' data-cost="{cost_v}" data-sold-for="{sold_v}" data-date="{date_v}" data-idx="{idx}">'
                '<td>{artist_d}</td>'
                '<td>{album_d}</td>'
                '<td>{cost_d}</td>'
                '<td>{sold_d}</td>'
                '<td class="{profit_class}">{profit_d}</td>'
                '<td>{date}</td>'
                '<td>{loc}</td>'
                '</tr>'
            ).format(
                sf=sf_key,
                artist=_html.escape(r['artist'].lower()),
                album=_html.escape(r['album'].lower()),
                cost_v=r['cost_val'] if r['cost_val'] is not None else '',
                sold_v=r['sold_for_val'] if r['sold_for_val'] is not None else '',
                date_v=_html.escape(r['sold_date']),
                idx=idx,
                artist_d=_html.escape(r['artist']),
                album_d=_html.escape(r['album']),
                cost_d=_fmt_cost(r['cost'], r['cost_val']),
                sold_d=_fmt_cost(r['sold_for'], r['sold_for_val']),
                profit_class=profit_class,
                profit_d=_fmt_money(profit) if profit is not None else '',
                date=_html.escape(r['sold_date']),
                loc=_html.escape(r['sold_location']),
            )
            idx += 1

    return (
        sf_tabs +
        '<div class="rec-toolbar">'
        '<input type="text" class="rec-search" placeholder="Search artist or album&hellip;" '
        'id="rec-search-sold" autocomplete="off">'
        '<span class="rec-count" id="rec-count-sold"></span>'
        '</div>'
        '<div class="rec-table-wrap">'
        '<table class="rec-table" id="rec-table-sold">'
        '<thead><tr>'
        '<th class="sortable" data-col="artist">Artist</th>'
        '<th class="sortable" data-col="album">Album</th>'
        '<th class="sortable" data-col="cost">Bought For</th>'
        '<th class="sortable" data-col="sold-for">Sold For</th>'
        '<th class="sortable" data-col="sold-for">Profit</th>'
        '<th class="sortable" data-col="date">Date</th>'
        '<th>Location</th>'
        '</tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table>'
        '</div>'
    )
