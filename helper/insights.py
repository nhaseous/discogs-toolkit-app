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

    # Pie charts row — Genre Breakdown + Format Breakdown side by side
    pies_html = (
        '<div class="insights-pies-row">' +
        _genre_year_section(insights['genre_pie'], insights.get('decade_pie')) +
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
        # Genre Breakdown <-> Year Breakdown: lock the card height once (using the
        # taller of the two panels) so the in-place swap never resizes the card.
        'document.querySelectorAll(".insights-pie-toggle").forEach(function(wrap){'
        'var lock=function(){'
        'if(wrap._locked)return;'
        'var max=0;'
        'wrap.querySelectorAll(".insights-panel").forEach(function(p){'
        'var hidden=p.style.display==="none";'
        'if(hidden){p.style.visibility="hidden";p.style.display="";}'
        'max=Math.max(max,p.offsetHeight);'
        'if(hidden){p.style.display="none";p.style.visibility="";}'
        '});'
        'if(max>0){wrap.style.minHeight=max+"px";wrap._locked=true;}'
        '};'
        'lock();'
        'wrap.querySelectorAll(".insights-toggle-switch").forEach(function(btn){'
        'btn.addEventListener("click",function(){'
        'lock();'
        'wrap.querySelectorAll(".insights-panel").forEach(function(p){'
        'p.style.display=p.style.display==="none"?"":"none";'
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
        'wrap.querySelectorAll(".insights-panel").forEach(function(p){'
        'p.style.display=p.style.display==="none"?"":"none";'
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

def _genre_year_section(genre_pie, year_pie):
    """
    Genre Breakdown card that toggles to a Year Breakdown pie in place. The
    title carries a switch ("Genre Breakdown / Year" ⇄ "Year Breakdown /
    Genres"); clicking it swaps the two panels without resizing the card. Both
    legends are clickable filter rows, like the other pie charts. The Year pie
    shows the per-decade distribution and filters the grid by decade.
    """
    has_genre = genre_pie and sum(s['value'] for s in genre_pie) > 0
    has_year  = year_pie  and sum(s['value'] for s in year_pie)  > 0

    # Degrade gracefully if either side has no data: render a plain, non-toggling pie.
    if not has_genre:
        return _pie_section("Year Breakdown", year_pie, filter_field='decade') if has_year else ''
    if not has_year:
        return _pie_section("Genre Breakdown", genre_pie, filter_field='genres')

    def _panel(title, swap_label, segments, filter_field, active):
        style = '' if active else ' style="display:none"'
        cls = 'insights-panel' + (' insights-panel--active' if active else '')
        return (
            f'<div class="{cls}"{style}>'
            f'<div class="rec-breakdown-title insights-toggle-title">'
            f'<span class="rec-breakdown-title-text">{title} '
            f'<span class="insights-toggle-switch">/ {swap_label}</span>'
            f'</span>'
            f'</div>'
            f'<div class="rec-pie-wrap">'
            f'{_pie_svg(segments, filter_field=filter_field)}'
            f'<div class="rec-pie-legend">{_pie_legend_html(segments, filter_field)}</div>'
            f'</div>'
            f'</div>'
        )

    # insights-pie-toggle has its own handler that locks the card height (so the
    # swap never resizes it) and then swaps the two panels.
    return (
        '<div class="rec-breakdown-section insights-pie-toggle">'
        + _panel('Genre Breakdown', 'Year',  genre_pie, 'genres', active=True)
        + _panel('Year Breakdown',  'Genre', year_pie,  'decade', active=False)
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
        panel_edition = f'<div class="insights-panel" style="display:none">{_bar_chart_html(edition_pie, filter_field="format_tags")}</div>'
    else:
        toggle_cls = ''
        title = f'<div class="rec-breakdown-title">Format Breakdown</div>'
        panel_fmt = pie_block(format_pie, filter_field="format")
        panel_edition = ''

    return (
        f'<div class="rec-breakdown-section{toggle_cls}">'
        f'{title}'
        f'{panel_fmt}'
        f'{panel_edition}'
        f'<div class="insights-format-sub insights-format-sub--lower">Type</div>'
        f'{pie_block(release_type_pie, filter_field="format_tags", reverse=True)}'
        f'</div>'
    )
