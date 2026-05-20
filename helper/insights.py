import collections
import html as _html
import math

_PIE_COLORS = [
    '#e11d48', '#d97706', '#059669', '#2563eb', '#7c3aed',
    '#db2777', '#4b5563', '#ea580c', '#65a30d', '#0891b2'
]

def get_collection_insights(items, total_value=None):
    """
    Aggregates collection items into stats.
    total_value is the dict from the API: {'minimum': '...', 'median': '...', 'maximum': '...'}
    """
    genre_counts = collections.Counter()
    style_counts = collections.Counter()
    artist_counts = collections.Counter()
    label_counts = collections.Counter()
    format_counts = collections.Counter()
    release_type_counts = collections.Counter()
    edition_counts = collections.Counter()
    decade_counts = collections.Counter()
    added_year_counts = collections.Counter()

    _RELEASE_TYPES = {'EP', 'Album', 'Single', 'Compilation'}
    _EDITION_TAGS = {'Remastered', 'Deluxe Edition', 'Numbered', 'Club Edition',
                     'Record Store Day', 'Picture Disc', 'Unofficial Release', 'Test Pressing'}

    for item in items:
        for g in item.get('genres', []): genre_counts[g] += 1
        for s in item.get('styles', []): style_counts[s] += 1
        for l in item.get('labels', []): label_counts[l] += 1
        for f in item.get('format', []): format_counts[f] += 1
        for tag in item.get('format_tags', []):
            if tag in _RELEASE_TYPES:
                release_type_counts[tag] += 1
                break
        for tag in item.get('format_tags', []):
            if tag in _EDITION_TAGS:
                edition_counts[tag] += 1
        for a in item.get('artist', []): artist_counts[a] += 1

        year = item.get('year', 0)
        if year > 1900:
            decade = (year // 10) * 10
            decade_counts[decade] += 1
            # Stamp a decade label on the item so the card grid can be filtered
            # by decade (same mechanism as genre/format filters).
            item['decade'] = f'{decade}s'

        da = item.get('date_added', '')
        if da and len(da) >= 4:
            try:
                added_yr = int(da[:4])
                if added_yr > 1990:
                    added_year_counts[added_yr] += 1
                    item['added_year'] = str(added_yr)
            except (ValueError, TypeError):
                pass

    all_genres  = genre_counts.most_common()
    all_styles  = style_counts.most_common()
    all_artists = artist_counts.most_common()
    all_labels  = label_counts.most_common()

    def _make_pie(counter, limit=10, offset=0):
        return [
            {'name': name, 'value': count, 'color': _PIE_COLORS[(i + offset) % len(_PIE_COLORS)]}
            for i, (name, count) in enumerate(counter.most_common(limit))
            if count > 0
        ]

    # Decade pie: sorted by count (most common first), like the Genre Breakdown.
    # Names ("1980s") match the per-item 'decade' stamp for filtering.
    decade_pie = [
        {'name': f'{decade}s', 'value': count, 'color': _PIE_COLORS[i % len(_PIE_COLORS)]}
        for i, (decade, count) in enumerate(decade_counts.most_common())
        if count > 0
    ]

    # Added-year data: line graph uses year-ascending order; table uses count-descending
    added_year_data  = sorted(added_year_counts.items())          # [(year, count), ...]
    added_year_table = added_year_counts.most_common()            # [(year, count), ...]

    return {
        'all_genres': all_genres,
        'all_subgenres': all_styles,
        'all_artists': all_artists,
        'all_labels': all_labels,
        'genre_total': sum(genre_counts.values()),
        'style_total': sum(style_counts.values()),
        'artist_total': sum(artist_counts.values()),
        'label_total': sum(label_counts.values()),
        'genre_pie':        _make_pie(genre_counts,        offset=0),
        'decade_pie':       decade_pie,
        'format_pie':       _make_pie(format_counts,       offset=4),
        'release_type_pie': _make_pie(release_type_counts, offset=9),
        'edition_pie':      _make_pie(edition_counts,      offset=2),
        'added_year_data':  added_year_data,
        'added_year_table': added_year_table,
        'total_value': total_value,
    }

def render_insights_dashboard(insights, kind='collection'):
    """
    Returns HTML for the insights dashboard, matching rec-dash-group style.
    kind='collection' renders the full dashboard; kind='wantlist' renders only
    the Top 5 breakdown row (Sub-Genres/Genres toggle + Top Artists + Top Labels).
    """
    def stat_card(label, value, sub='', value_class=''):
        sub_html = f'<div class="rec-stat-sub">{sub}</div>' if sub else ''
        val_cls = 'rec-stat-value' + (' ' + value_class if value_class else '')
        return (
            f'<div class="rec-stat-card">'
            f'<div class="rec-stat-label">{label}</div>'
            f'<div class="{val_cls}">{value}</div>'
            f'{sub_html}'
            f'</div>'
        )

    # Value Banner (only if available)
    banner_html = ""
    tv = insights.get('total_value')
    if tv:
        banner_html = (
            '<div class="rec-stat-grid">' +
            stat_card("Minimum Value", tv.get('minimum', '—')) +
            stat_card("Median Value", tv.get('median', '—'), value_class="rec-stat-value--pos") +
            stat_card("Maximum Value", tv.get('maximum', '—')) +
            '</div>'
        )

    # Pie charts row — Genre/Year/Added History (3-state) + Format Breakdown side by side
    pies_html = (
        '<div class="insights-pies-row">' +
        _genre_year_added_section(
            insights['genre_pie'],
            insights.get('decade_pie'),
            insights.get('added_year_data', []),
            insights.get('added_year_table', []),
        ) +
        _format_breakdown_section(insights['format_pie'], insights['release_type_pie'], insights.get('edition_pie')) +
        '</div>'
    )

    def make_rows(data, total, filter_field=None, primary=5):
        rows = ""
        for i, (name, val) in enumerate(data):
            pct = val / total * 100 if total else 0
            classes = []
            if filter_field: classes.append('insights-filter-row')
            if i >= primary: classes.append('rec-breakdown-row-extra')
            attrs = ''
            if classes: attrs += f' class="{" ".join(classes)}"'
            if filter_field:
                attrs += (f' data-filter-field="{_html.escape(filter_field)}"'
                          f' data-filter-value="{_html.escape(str(name))}"')
            rows += (
                f'<tr{attrs}>'
                f'<td class="rec-sf-name">{_html.escape(name)}</td>'
                f'<td class="rec-sf-money">{val} items'
                f'<span style="color:var(--ink-muted);margin-left:6px">{pct:.0f}%</span>'
                f'</td>'
                f'</tr>'
            )
        return rows

    def _expand_toggle():
        return '<span class="breakdown-expand" title="Show all">+</span>'

    def top_table(title, data, total=None, filter_field=None, expandable=True):
        rows = make_rows(data, total, filter_field=filter_field) if data else ''
        has_extras = expandable and len(data) > 5
        section_cls = 'rec-breakdown-section'
        if has_extras: section_cls += ' breakdown-expandable'
        title_inner = f'<span class="rec-breakdown-title-text">{title}</span>' + (_expand_toggle() if has_extras else '')
        title_cls = 'rec-breakdown-title' + (' rec-breakdown-title--row' if has_extras else '')
        return (
            f'<div class="{section_cls}">'
            f'<div class="{title_cls}">{title_inner}</div>'
            f'<div class="rec-breakdown-scroll">'
            f'<table class="rec-breakdown-table"><tbody>{rows}</tbody></table>'
            f'</div>'
            f'</div>'
        )

    def genre_toggle_section():
        sub_data   = insights['all_subgenres']
        genre_data = insights['all_genres']
        subgenre_rows = make_rows(sub_data,   insights['style_total'], filter_field='styles')
        genre_rows    = make_rows(genre_data, insights['genre_total'], filter_field='genres')
        sub_has_extras   = len(sub_data) > 5
        genre_has_extras = len(genre_data) > 5

        def _panel(label_main, swap_label, rows_html, has_extras, active):
            style = '' if active else ' style="display:none"'
            cls = 'insights-panel' + (' insights-panel--active' if active else '')
            section_extra = ' breakdown-expandable' if has_extras else ''
            expand_btn = _expand_toggle() if has_extras else ''
            return (
                f'<div class="{cls}{section_extra}"{style}>'
                f'<div class="rec-breakdown-title rec-breakdown-title--row insights-toggle-title">'
                f'<span class="rec-breakdown-title-text">{label_main} '
                f'<span class="insights-toggle-switch">/ {swap_label}</span>'
                f'</span>'
                f'{expand_btn}'
                f'</div>'
                f'<div class="rec-breakdown-scroll">'
                f'<table class="rec-breakdown-table"><tbody>{rows_html}</tbody></table>'
                f'</div>'
                f'</div>'
            )

        return (
            '<div class="rec-breakdown-section insights-genre-toggle">'
            + _panel('Top Sub-Genres', 'Genres',     subgenre_rows, sub_has_extras,   active=True)
            + _panel('Top Genres',     'Sub-Genres', genre_rows,    genre_has_extras, active=False)
            + '</div>'
        )

    breakdown_html = (
        '<div class="rec-breakdown">' +
        genre_toggle_section() +
        top_table("Top Artists", insights['all_artists'], total=insights['artist_total'], filter_field='artist') +
        top_table("Top Labels",  insights['all_labels'],  total=insights['label_total'],  filter_field='labels') +
        '</div>'
    )

    toggle_script = (
        '<script>'
        'document.addEventListener("DOMContentLoaded",function(){'
        'document.querySelectorAll(".insights-three-toggle").forEach(function(wrap){'
        # Panels live in a CSS grid (all in grid-row:1, grid-column:1) so they stack
        # and the card height = max(genre, year) at all times. We use visibility
        # instead of display to toggle them so they keep their space in the grid.
        # lock() just reads wrap.offsetHeight (already correct) to size the scroll area.
        'var lock=function(){'
        'if(wrap._locked)return;'
        'var titleH=34,graphH=82;'
        'var addedPanel=wrap.querySelector(":scope>[data-panel=\'added\']");'
        'var scrollEl=addedPanel?addedPanel.querySelector(".insights-added-scroll"):null;'
        'if(scrollEl){scrollEl.style.maxHeight="0";scrollEl.style.overflow="hidden";}'
        'var wrapH=wrap.offsetHeight;'
        'if(addedPanel){'
        'var tEl=addedPanel.querySelector(".rec-breakdown-title");'
        'var gEl=addedPanel.querySelector(".insights-line-graph-wrap");'
        'if(tEl)titleH=tEl.offsetHeight+10;'
        'if(gEl)graphH=gEl.offsetHeight+10;'
        '}'
        'if(wrapH>0){'
        'if(scrollEl){'
        'scrollEl.style.maxHeight=Math.max(60,wrapH-titleH-graphH)+"px";'
        'scrollEl.style.overflow="";'
        'scrollEl.style.overflowY="auto";'
        '}'
        'wrap._locked=true;'
        '}'
        '};'
        'lock();'
        'wrap.querySelectorAll(".insights-toggle-switch").forEach(function(btn){'
        'btn.addEventListener("click",function(){'
        'var target=btn.dataset.goto;'
        'lock();'
        # When navigating TO the genre panel, update its back-toggle to reflect
        # the source panel so "/ Year" vs "/ Added" is always contextually correct.
        'if(target==="genre"){'
        'var src=null;'
        'wrap.querySelectorAll(":scope>.insights-panel").forEach(function(p){'
        'if(p.style.visibility!=="hidden")src=p.dataset.panel;'
        '});'
        'if(src){'
        'var gb=wrap.querySelector(":scope>[data-panel=\'genre\'] .insights-genre-back");'
        'if(gb){gb.dataset.goto=src;gb.textContent=src==="year"?"/ Year":"/ Added";}'
        '}'
        '}'
        'wrap.querySelectorAll(":scope>.insights-panel").forEach(function(p){'
        'var active=p.dataset.panel===target;'
        'p.style.visibility=active?"":"hidden";'
        'p.style.pointerEvents=active?"":"none";'
        '});'
        '});'
        '});'
        '});'
        'document.querySelectorAll(".insights-genre-toggle").forEach(function(wrap){'
        'wrap.querySelectorAll(".insights-toggle-switch").forEach(function(btn){'
        'btn.addEventListener("click",function(){'
        'wrap.querySelectorAll(".insights-panel").forEach(function(p){'
        'p.style.display=p.style.display==="none"?"":"none";'
        '});'
        '});'
        '});'
        '});'
        'document.querySelectorAll(".insights-format-toggle").forEach(function(wrap){'
        'wrap.querySelectorAll(".insights-toggle-switch").forEach(function(btn){'
        'btn.addEventListener("click",function(){'
        'wrap.querySelectorAll(".insights-format-panels-wrap>.insights-panel").forEach(function(p){'
        'var hidden=p.style.visibility==="hidden";'
        'p.style.visibility=hidden?"":"hidden";'
        'p.style.pointerEvents=hidden?"":"none";'
        '});'
        'btn.textContent=btn.textContent==="More"?"Less":"More";'
        '});'
        '});'
        '});'
        '});'
        '</script>'
    )

    if kind == 'wantlist':
        dash_id = 'wantlist-insights-dash'
        content = breakdown_html
        script = ''  # collection dashboard's script already binds both toggle wraps
        # Hidden by default — collection (or list) is the active tab on page load,
        # so the wantlist dashboard would otherwise flash before _onLookupTabChange hides it.
        style_attr = ' style="display:none"'
    else:
        dash_id = 'collection-insights-dash'
        content = banner_html + pies_html + breakdown_html
        script = toggle_script
        style_attr = ''

    return (
        '<div class="rec-dash-group" id="' + dash_id + '"' + style_attr + '>' +
        content +
        '</div>' +
        script
    )

def _pie_svg(segments, size=110, extra_class='', filter_field=None):
    total = sum(s['value'] for s in segments)
    if total == 0: return ''
    cx, cy, r = size/2, size/2, size/2 - 2
    paths = []
    angle = -90
    for seg in segments:
        if seg['value'] == 0: continue
        sweep = (seg['value'] / total) * 360
        if sweep >= 360: sweep = 359.99
        end_angle = angle + sweep
        x1 = cx + r * math.cos(math.radians(angle))
        y1 = cy + r * math.sin(math.radians(angle))
        x2 = cx + r * math.cos(math.radians(end_angle))
        y2 = cy + r * math.sin(math.radians(end_angle))
        large_arc = 1 if sweep > 180 else 0
        d = f"M {cx} {cy} L {x1} {y1} A {r} {r} 0 {large_arc} 1 {x2} {y2} Z"
        path_cls = 'rec-pie-path'
        ff = ''
        if filter_field:
            path_cls += ' insights-filter-row'
            ff = (f' data-filter-field="{_html.escape(filter_field)}"'
                  f' data-filter-value="{_html.escape(str(seg["name"] or ""))}"')
        paths.append(f'<path class="{path_cls}" d="{d}" fill="{seg["color"]}" stroke="var(--paper)" stroke-width="2"{ff}/>')
        angle = end_angle
    svg_cls = f'rec-pie-svg{" " + extra_class if extra_class else ""}'
    return f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" class="{svg_cls}">{"".join(paths)}</svg>'

def _pie_legend_html(segments, filter_field=None):
    total = sum(s['value'] for s in segments)
    if total == 0: return ''
    items = []
    for seg in segments:
        if seg['value'] <= 0: continue
        cls = 'rec-pie-legend-item'
        ff = ''
        if filter_field:
            cls += ' insights-filter-row'
            ff = (f' data-filter-field="{_html.escape(filter_field)}"'
                  f' data-filter-value="{_html.escape(str(seg["name"] or ""))}"')
        items.append(
            f'<div class="{cls}"{ff}>'
            f'<span class="rec-pie-dot" style="background:{seg["color"]}"></span>'
            f'<span class="rec-pie-name">{_html.escape(seg["name"] or "—")}</span>'
            f'<span class="rec-pie-pct">{seg["value"] / total * 100:.0f}%</span>'
            f'</div>'
        )
    return ''.join(items)

def _bar_chart_html(segments, filter_field=None):
    if not segments: return ''
    max_val = max((s['value'] for s in segments if s['value'] > 0), default=0)
    if max_val == 0: return ''
    rows = []
    for seg in segments:
        if seg['value'] <= 0: continue
        pct_of_max = seg['value'] / max_val * 100
        cls = 'insights-bar-row'
        ff = ''
        if filter_field:
            cls += ' insights-filter-row'
            ff = (f' data-filter-field="{_html.escape(filter_field)}"'
                  f' data-filter-value="{_html.escape(str(seg["name"] or ""))}"')
        rows.append(
            f'<div class="{cls}"{ff}>'
            f'<div class="insights-bar-label">{_html.escape(seg["name"] or "—")}</div>'
            f'<div class="insights-bar-track">'
            f'<div class="insights-bar-fill" style="width:{pct_of_max:.1f}%;background:{seg["color"]}"></div>'
            f'</div>'
            f'<div class="insights-bar-count">{seg["value"]} items</div>'
            f'</div>'
        )
    return f'<div class="insights-bar-chart">{"".join(rows)}</div>'

def _pie_section(title, segments, filter_field=None):
    if not segments or sum(s['value'] for s in segments) == 0: return ''
    return (
        f'<div class="rec-breakdown-section">'
        f'<div class="rec-breakdown-title">{title}</div>'
        f'<div class="rec-pie-wrap">'
        f'{_pie_svg(segments, filter_field=filter_field)}'
        f'<div class="rec-pie-legend">{_pie_legend_html(segments, filter_field)}</div>'
        f'</div>'
        f'</div>'
    )

def _line_graph_svg(year_data):
    """SVG line graph for added-year history. year_data: [(year, count), ...] sorted ascending."""
    if not year_data:
        return ''
    years  = [d[0] for d in year_data]
    counts = [d[1] for d in year_data]
    n = len(years)
    raw_max = max(counts) if counts else 1

    # Compute a nice step size so 5 equally-spaced labels land on round numbers:
    # labels = [0, step, 2*step, 3*step, 4*step=nice_top], with 4*step >= raw_max.
    if raw_max <= 0:
        nice_step, nice_top = 1, 4
    else:
        _min_step = raw_max / 4
        if _min_step < 1:
            nice_step = 1
        else:
            _mag  = 10 ** math.floor(math.log10(_min_step))
            _norm = _min_step / _mag
            _cands = [1, 1.5, 2, 2.5, 5, 10]
            _s = next(s for s in _cands if s >= _norm) * _mag
            nice_step = int(_s) if _s == int(_s) else _s
        nice_top = nice_step * 4
    max_count = nice_top   # always >= raw_max by construction

    # Chart height is driven by label count: each of the 5 y-axis labels gets ROW_H px,
    # so the 4 inter-gridline intervals end up slightly larger than ROW_H.
    NUM_LABELS = 5
    ROW_H = 18
    VW    = 260
    PL_DATA   = 40
    Y_LABEL_X = 20
    GRID_X1   = Y_LABEL_X + 5   # gridlines start just after y-axis labels
    PT, PB  = 12, 22

    ch = (NUM_LABELS - 1) * ROW_H   # 4 intervals × 18 px = 72 px
    VH = PT + ch + PB

    # X-axis labels: computed before pts so we know whether the final year is
    # dropped, which determines the right padding (PR_DATA).
    max_labels = 7
    if n <= max_labels:
        label_indices = list(range(n))
    else:
        step = math.ceil((n - 1) / (max_labels - 1))
        label_indices = list(range(0, n, step))
        if label_indices[-1] != n - 1 and len(label_indices) < 3:
            label_indices.append(n - 1)

    # When the final year label is dropped, set PR_DATA=0 so xi(n-1) lands
    # exactly at VW — the last point reaches the gridline edge at natural spacing.
    # Otherwise keep the normal right inset so the last dot isn't flush with the edge.
    dropped_final = n > max_labels and label_indices[-1] != n - 1
    PR_DATA = 0 if dropped_final else 16

    cw_data = VW - PL_DATA - PR_DATA  # chart data spans PL_DATA → VW-PR_DATA

    def xi(i):
        return PL_DATA + (i * cw_data / (n - 1) if n > 1 else cw_data / 2)

    def yi(v):
        return PT + ch * (1 - v / max_count) if max_count else PT + ch

    pts     = [(xi(i), yi(counts[i])) for i in range(n)]
    pts_str = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)

    # Filled area under the line
    area_d = (
        f'M {pts[0][0]:.1f},{PT + ch:.1f} '
        + ' '.join(f'L {x:.1f},{y:.1f}' for x, y in pts)
        + f' L {pts[-1][0]:.1f},{PT + ch:.1f} Z'
    )

    # Gridlines run from PL_DATA to VW (the chart data column, not the label gutter).
    # Y-axis labels at x=2 (text-anchor="start") in the left gutter.
    grid_parts = []
    y_label_vals = [nice_top, nice_step * 3, nice_step * 2, nice_step, 0]
    for gv in y_label_vals:
        gy = yi(gv)
        grid_parts.append(
            f'<line x1="{GRID_X1}" y1="{gy:.1f}" x2="{VW}" y2="{gy:.1f}" '
            f'stroke="var(--rule)" stroke-width="1"/>'
        )
        grid_parts.append(
            f'<text x="{Y_LABEL_X}" y="{gy:.1f}" text-anchor="end" dominant-baseline="middle" '
            f'font-size="9" fill="var(--ink-muted)">{gv}</text>'
        )

    label_parts = []
    for pos, i in enumerate(label_indices):
        is_last = pos == len(label_indices) - 1
        if is_last and i == n - 1:
            # Last label is the final data point: pin to right edge
            x_pos = float(VW)
            anchor = 'end'
        else:
            x_pos = xi(i)
            anchor = 'middle'
        label_parts.append(
            f'<text x="{x_pos:.1f}" y="{VH - 4}" text-anchor="{anchor}" '
            f'font-size="9" fill="var(--ink-muted)">{years[i]}</text>'
        )

    # Data point dots
    dot_parts = [
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="var(--rust)"/>'
        for x, y in pts
    ]

    return (
        f'<svg viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg" '
        f'class="insights-line-graph-svg" overflow="visible">'
        f'<path d="{area_d}" fill="var(--rust)" opacity="0.12"/>'
        + ''.join(grid_parts)
        + f'<polyline points="{pts_str}" fill="none" stroke="var(--rust)" '
        f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        + ''.join(dot_parts)
        + ''.join(label_parts)
        + '</svg>'
    )


def _genre_year_added_section(genre_pie, year_pie, added_year_data, added_year_table):
    """
    3-state card replacing the old 2-state Genre/Year toggle.

    State 1 (default): Year Breakdown — decade pie + "Added" right button
    State 2:           Added History  — line graph + scrollable added-year table
                       inline "/ Genre" toggle + "Released" right button
    State 3:           Genre Breakdown — genre pie, inline "/ Added" toggle, no right button

    The JS handler (.insights-three-toggle) locks the card height to the tallest
    panel and dynamically sets the scroll-container max-height for Added History.
    """
    has_genre = genre_pie and sum(s['value'] for s in genre_pie) > 0
    has_year  = year_pie  and sum(s['value'] for s in year_pie)  > 0
    has_added = bool(added_year_data)

    if not has_genre and not has_year and not has_added:
        return ''

    # Minimal degradation paths
    if not has_year and not has_added:
        return _pie_section("Genre Breakdown", genre_pie, filter_field='genres')
    if not has_genre and not has_added:
        return _pie_section("Year Breakdown", year_pie, filter_field='decade')

    # ── Panel 1: Year Breakdown ──────────────────────────────────────────────
    year_pie_html = (
        f'<div class="rec-pie-wrap">'
        f'{_pie_svg(year_pie, filter_field="decade") if has_year else ""}'
        f'<div class="rec-pie-legend">'
        f'{_pie_legend_html(year_pie, filter_field="decade") if has_year else ""}'
        f'</div>'
        f'</div>'
    )
    genre_btn_from_year = (
        f'<span class="insights-toggle-switch" data-goto="genre">/ Genre</span>'
        if has_genre else ''
    )
    added_btn = (
        f'<span class="insights-toggle-switch" data-goto="added">Added</span>'
        if has_added else ''
    )
    panel_year = (
        f'<div class="insights-panel" data-panel="year" style="visibility:hidden;pointer-events:none">'
        f'<div class="rec-breakdown-title insights-toggle-title">'
        f'<span class="rec-breakdown-title-text">Year Breakdown {genre_btn_from_year}</span>'
        f'{added_btn}'
        f'</div>'
        f'{year_pie_html}'
        f'</div>'
    )

    # ── Panel 2: Added History ───────────────────────────────────────────────
    line_graph = _line_graph_svg(added_year_data) if has_added else ''
    total_added = sum(c for _, c in added_year_table)
    year_rows = ''
    for yr, cnt in added_year_table:
        pct = cnt / total_added * 100 if total_added else 0
        year_rows += (
            f'<tr class="insights-filter-row"'
            f' data-filter-field="added_year"'
            f' data-filter-value="{_html.escape(str(yr))}">'
            f'<td class="rec-sf-name">{_html.escape(str(yr))}</td>'
            f'<td class="rec-sf-money">{cnt} items'
            f'<span style="color:var(--ink-muted);margin-left:6px">{pct:.0f}%</span>'
            f'</td>'
            f'</tr>'
        )
    genre_inline_btn = (
        f'<span class="insights-toggle-switch" data-goto="genre">/ Genre</span>'
        if has_genre else ''
    )
    panel_added = (
        f'<div class="insights-panel" data-panel="added" style="visibility:hidden;pointer-events:none">'
        f'<div class="rec-breakdown-title insights-toggle-title">'
        f'<span class="rec-breakdown-title-text">Added History {genre_inline_btn}</span>'
        f'<span class="insights-toggle-switch" data-goto="year">Released</span>'
        f'</div>'
        f'<div class="insights-line-graph-wrap">{line_graph}</div>'
        f'<div class="insights-added-scroll">'
        f'<table class="rec-breakdown-table"><tbody>{year_rows}</tbody></table>'
        f'</div>'
        f'</div>'
    )

    # ── Panel 3: Genre Breakdown ─────────────────────────────────────────────
    genre_pie_html = (
        f'<div class="rec-pie-wrap">'
        f'{_pie_svg(genre_pie, filter_field="genres") if has_genre else ""}'
        f'<div class="rec-pie-legend">'
        f'{_pie_legend_html(genre_pie, filter_field="genres") if has_genre else ""}'
        f'</div>'
        f'</div>'
    )
    # Genre back-toggle defaults to "/ Year". JS updates its text + data-goto at
    # navigation time based on which panel the user came from.
    genre_back_btn = (
        f'<span class="insights-toggle-switch insights-genre-back" data-goto="year">/ Year</span>'
        if (has_year or has_added) else ''
    )
    panel_genre = (
        f'<div class="insights-panel insights-panel--active" data-panel="genre">'
        f'<div class="rec-breakdown-title insights-toggle-title">'
        f'<span class="rec-breakdown-title-text">Genre Breakdown {genre_back_btn}</span>'
        f'</div>'
        f'{genre_pie_html}'
        f'</div>'
    )

    return (
        '<div class="rec-breakdown-section insights-three-toggle">'
        + panel_year
        + panel_added
        + panel_genre
        + '</div>'
    )

def _format_breakdown_section(format_pie, release_type_pie, edition_pie=None):
    if not format_pie and not release_type_pie: return ''

    def pie_block(segments, filter_field=None, reverse=False):
        if not segments: return ''
        svg = _pie_svg(segments, size=80, extra_class='rec-pie-svg--sm', filter_field=filter_field)
        legend = f'<div class="rec-pie-legend">{_pie_legend_html(segments, filter_field)}</div>'
        cls = 'rec-pie-wrap rec-pie-wrap--reverse' if reverse else 'rec-pie-wrap'
        return f'<div class="{cls}">{svg}{legend}</div>'

    if edition_pie:
        toggle_cls = ' insights-format-toggle'
        title = (
            f'<div class="rec-breakdown-title insights-toggle-title">'
            f'Format Breakdown'
            f'<span class="insights-toggle-switch">More</span>'
            f'</div>'
        )
        panel_fmt = f'<div class="insights-panel">{pie_block(format_pie, filter_field="format")}</div>'
        panel_edition = f'<div class="insights-panel" style="visibility:hidden;pointer-events:none">{_bar_chart_html(edition_pie, filter_field="format_tags")}</div>'
        panels_html = f'<div class="insights-format-panels-wrap">{panel_fmt}{panel_edition}</div>'
    else:
        toggle_cls = ''
        title = f'<div class="rec-breakdown-title">Format Breakdown</div>'
        panels_html = pie_block(format_pie, filter_field="format")

    return (
        f'<div class="rec-breakdown-section{toggle_cls}">'
        f'{title}'
        f'{panels_html}'
        f'<div class="insights-format-sub insights-format-sub--lower">Type</div>'
        f'{pie_block(release_type_pie, filter_field="format_tags", reverse=True)}'
        f'</div>'
    )
