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
    decade_counts = collections.Counter()

    _RELEASE_TYPES = {'EP', 'Album', 'Single'}

    demand_factors = []
    for item in items:
        have = item.get('have', 0)
        want = item.get('want', 0)
        factor = want / (have + 1)
        demand_factors.append(factor)

        for g in item.get('genres', []): genre_counts[g] += 1
        for s in item.get('styles', []): style_counts[s] += 1
        for l in item.get('labels', []): label_counts[l] += 1
        for f in item.get('format', []): format_counts[f] += 1
        for tag in item.get('format_tags', []):
            if tag in _RELEASE_TYPES:
                release_type_counts[tag] += 1
                break
        for a in item.get('artist', []): artist_counts[a] += 1

        year = item.get('year', 0)
        if year > 1900:
            decade = (year // 10) * 10
            decade_counts[decade] += 1

    # Genre Value Approximation
    genre_values = {}
    if total_value and total_value.get('median'):
        try:
            total_median = float(total_value['median'].replace('$', '').replace(',', '').strip())
        except (ValueError, AttributeError):
            total_median = 0
            
        if total_median > 0:
            # Distribute total_median across items based on demand factors
            total_demand = sum(demand_factors)
            if total_demand > 0:
                # Value per item = total_median * (item_demand / total_demand)
                # Value per genre = sum of values of items in that genre
                for i, item in enumerate(items):
                    item_value = total_median * (demand_factors[i] / total_demand)
                    # Since items can have multiple genres, we split the item's value equally among them
                    gs = item.get('genres', [])
                    if gs:
                        val_per_genre = item_value / len(gs)
                        for g in gs:
                            genre_values[g] = genre_values.get(g, 0) + val_per_genre

    top_genres = genre_counts.most_common(5)
    top_styles = style_counts.most_common(5)
    top_artists = artist_counts.most_common(5)
    top_labels = label_counts.most_common(5)

    decades_sorted = sorted(decade_counts.items())
    
    def _make_pie(counter, limit=10, offset=0):
        return [
            {'name': name, 'value': count, 'color': _PIE_COLORS[(i + offset) % len(_PIE_COLORS)]}
            for i, (name, count) in enumerate(counter.most_common(limit))
            if count > 0
        ]

    return {
        'top_genres': top_genres,
        'top_subgenres': top_styles,
        'top_artists': top_artists,
        'top_labels': top_labels,
        'genre_total': sum(genre_counts.values()),
        'style_total': sum(style_counts.values()),
        'artist_total': sum(artist_counts.values()),
        'label_total': sum(label_counts.values()),
        'decades': decades_sorted,
        'genre_pie':        _make_pie(genre_counts,        offset=0),
        'format_pie':       _make_pie(format_counts,       offset=4),
        'release_type_pie': _make_pie(release_type_counts, offset=9),
        'genre_values': genre_values,
        'total_value': total_value,
    }

def render_insights_dashboard(insights):
    """
    Returns HTML for the insights dashboard, matching rec-dash-group style.
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
        _pie_section("Genre Breakdown", insights['genre_pie'], filter_field='genres') +
        _format_breakdown_section(insights['format_pie'], insights['release_type_pie']) +
        '</div>'
    )

    def make_rows(data, total, filter_field=None):
        rows = ""
        for name, val in data:
            pct = val / total * 100 if total else 0
            ff = (f' class="insights-filter-row"'
                  f' data-filter-field="{_html.escape(filter_field)}"'
                  f' data-filter-value="{_html.escape(str(name))}"') if filter_field else ''
            rows += (
                f'<tr{ff}>'
                f'<td class="rec-sf-name">{_html.escape(name)}</td>'
                f'<td class="rec-sf-money">{val} items'
                f'<span style="color:var(--ink-muted);margin-left:6px">{pct:.0f}%</span>'
                f'</td>'
                f'</tr>'
            )
        return rows

    def top_table(title, data, value_suffix="", is_currency=False, total=None, filter_field=None):
        if is_currency:
            rows = ""
            for name, val in data:
                rows += (
                    f'<tr>'
                    f'<td class="rec-sf-name">{_html.escape(name)}</td>'
                    f'<td class="rec-sf-money">${val:,.2f}</td>'
                    f'</tr>'
                )
        else:
            rows = make_rows(data, total, filter_field=filter_field)
        return (
            f'<div class="rec-breakdown-section">'
            f'<div class="rec-breakdown-title">{title}</div>'
            f'<table class="rec-breakdown-table"><tbody>{rows}</tbody></table>'
            f'</div>'
        )

    def genre_toggle_section():
        subgenre_rows = make_rows(insights['top_subgenres'], insights['style_total'], filter_field='styles')
        genre_rows    = make_rows(insights['top_genres'],    insights['genre_total'],  filter_field='genres')
        return (
            f'<div class="rec-breakdown-section insights-genre-toggle">'
            f'<div class="insights-panel insights-panel--active">'
            f'<div class="rec-breakdown-title insights-toggle-title">'
            f'Top Sub-genres'
            f'<span class="insights-toggle-switch">Genre</span>'
            f'</div>'
            f'<table class="rec-breakdown-table"><tbody>{subgenre_rows}</tbody></table>'
            f'</div>'
            f'<div class="insights-panel" style="display:none">'
            f'<div class="rec-breakdown-title insights-toggle-title">'
            f'Top Genres'
            f'<span class="insights-toggle-switch">Sub-genre</span>'
            f'</div>'
            f'<table class="rec-breakdown-table"><tbody>{genre_rows}</tbody></table>'
            f'</div>'
            f'</div>'
        )

    # Value per Genre Table (Approximated)
    value_genre_html = ""
    if insights['genre_values']:
        sorted_val_genres = sorted(insights['genre_values'].items(), key=lambda x: x[1], reverse=True)[:5]
        value_genre_html = top_table("Value per Genre (Top 5)", sorted_val_genres, is_currency=True)
        value_genre_html = value_genre_html.replace('rec-breakdown-section', 'rec-breakdown-section rec-breakdown-section--wide', 1)
        value_genre_html = value_genre_html.replace('</div><table', '<div class="rec-stat-sub" style="margin-bottom:8px">Approximated based on have/want data</div><table', 1)

    breakdown_html = (
        '<div class="rec-breakdown">' +
        genre_toggle_section() +
        top_table("Top Artists", insights['top_artists'], " items", total=insights['artist_total'], filter_field='artist') +
        top_table("Top Labels",  insights['top_labels'],  " items", total=insights['label_total'],  filter_field='labels') +
        '</div>' +
        value_genre_html
    )

    toggle_script = (
        '<script>'
        '(function(){'
        'document.querySelectorAll(".insights-genre-toggle").forEach(function(wrap){'
        'wrap.querySelectorAll(".insights-toggle-switch").forEach(function(btn){'
        'btn.addEventListener("click",function(){'
        'wrap.querySelectorAll(".insights-panel").forEach(function(p){'
        'p.style.display=p.style.display==="none"?"":"none";'
        '});'
        '});'
        '});'
        '});'
        '})();'
        '</script>'
    )

    return (
        '<div class="rec-dash-group" id="collection-insights-dash">' +
        banner_html +
        pies_html +
        breakdown_html +
        '</div>' +
        toggle_script
    )

def _pie_svg(segments, size=110, extra_class=''):
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
        paths.append(f'<path d="{d}" fill="{seg["color"]}" stroke="var(--paper)" stroke-width="2"/>')
        angle = end_angle
    cls = f'rec-pie-svg{" " + extra_class if extra_class else ""}'
    return f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" class="{cls}">{"".join(paths)}</svg>'

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

def _pie_section(title, segments, filter_field=None):
    if not segments or sum(s['value'] for s in segments) == 0: return ''
    return (
        f'<div class="rec-breakdown-section">'
        f'<div class="rec-breakdown-title">{title}</div>'
        f'<div class="rec-pie-wrap">'
        f'{_pie_svg(segments)}'
        f'<div class="rec-pie-legend">{_pie_legend_html(segments, filter_field)}</div>'
        f'</div>'
        f'</div>'
    )

def _format_breakdown_section(format_pie, release_type_pie):
    if not format_pie and not release_type_pie: return ''

    def pie_block(segments, filter_field=None, reverse=False):
        if not segments: return ''
        svg = _pie_svg(segments, size=80, extra_class='rec-pie-svg--sm')
        legend = f'<div class="rec-pie-legend">{_pie_legend_html(segments, filter_field)}</div>'
        cls = 'rec-pie-wrap rec-pie-wrap--reverse' if reverse else 'rec-pie-wrap'
        return f'<div class="{cls}">{svg}{legend}</div>'

    return (
        f'<div class="rec-breakdown-section">'
        f'<div class="rec-breakdown-title">Format Breakdown</div>'
        f'{pie_block(format_pie, filter_field="format", reverse=False)}'
        f'<div class="insights-format-sub insights-format-sub--lower">Type</div>'
        f'{pie_block(release_type_pie, filter_field="format_tags", reverse=True)}'
        f'</div>'
    )
