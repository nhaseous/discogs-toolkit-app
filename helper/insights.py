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
    decade_counts = collections.Counter()
    
    # Weighting: compute "Demand Factor" per item
    # Demand = Want / (Have + 1)
    demand_factors = []
    for item in items:
        have = item.get('have', 0)
        want = item.get('want', 0)
        # Avoid division by zero, use +1 smoothing
        factor = want / (have + 1)
        demand_factors.append(factor)
        
        for g in item.get('genres', []): genre_counts[g] += 1
        for s in item.get('styles', []): style_counts[s] += 1
        if item.get('artist'): artist_counts[item['artist']] += 1
        
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

    # Format for rendering
    top_genres = genre_counts.most_common(5)
    top_styles = style_counts.most_common(5)
    top_artists = artist_counts.most_common(5)
    
    decades_sorted = sorted(decade_counts.items())
    
    # Pie segments
    total_genre_items = sum(genre_counts.values())
    genre_pie = []
    if total_genre_items > 0:
        for i, (name, count) in enumerate(genre_counts.most_common(10)):
            genre_pie.append({
                'name': name,
                'value': count,
                'color': _PIE_COLORS[i % len(_PIE_COLORS)]
            })

    return {
        'top_genres': top_genres,
        'top_subgenres': top_styles,
        'top_artists': top_artists,
        'genre_total': sum(genre_counts.values()),
        'style_total': sum(style_counts.values()),
        'artist_total': sum(artist_counts.values()),
        'decades': decades_sorted,
        'genre_pie': genre_pie,
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

    # Pie Chart Section
    pie_html = _pie_section("Genre Breakdown", insights['genre_pie'])

    # Top 5 Tables
    def top_table(title, data, value_suffix="", is_currency=False, total=None):
        rows = ""
        for name, val in data:
            if is_currency:
                val_str = f"${val:,.2f}"
            elif total:
                pct = val / total * 100
                val_str = (
                    f'{val}{value_suffix}'
                    f'<span style="color:var(--ink-muted);margin-left:6px">{pct:.0f}%</span>'
                )
            else:
                val_str = f"{val}{value_suffix}"
            rows += (
                f'<tr>'
                f'<td class="rec-sf-name">{_html.escape(name)}</td>'
                f'<td class="rec-sf-money">{val_str}</td>'
                f'</tr>'
            )
        return (
            f'<div class="rec-breakdown-section">'
            f'<div class="rec-breakdown-title">{title}</div>'
            f'<table class="rec-breakdown-table"><tbody>{rows}</tbody></table>'
            f'</div>'
        )

    # Value per Genre Table (Approximated)
    value_genre_html = ""
    if insights['genre_values']:
        # Sort by value descending
        sorted_val_genres = sorted(insights['genre_values'].items(), key=lambda x: x[1], reverse=True)[:5]
        value_genre_html = top_table("Value per Genre (Top 5)", sorted_val_genres, is_currency=True)
        # Match the style and include disclaimer
        value_genre_html = value_genre_html.replace('rec-breakdown-section', 'rec-breakdown-section rec-breakdown-section--wide', 1)
        value_genre_html = value_genre_html.replace('</div><table', '<div class="rec-stat-sub" style="margin-bottom:8px">Approximated based on have/want data</div><table', 1)

    breakdown_html = (
        '<div class="rec-breakdown">' +
        top_table("Top Genres", insights['top_genres'], " items", total=insights['genre_total']) +
        top_table("Top Sub-genres", insights['top_subgenres'], " items", total=insights['style_total']) +
        top_table("Top Artists", insights['top_artists'], " items", total=insights['artist_total']) +
        '</div>' + 
        value_genre_html
    )

    return (
        '<div class="rec-dash-group" id="collection-insights-dash">' +
        banner_html +
        pie_html +
        breakdown_html +
        '</div>'
    )

# Private helpers copied/adapted from records.py for consistency

def _pie_svg(segments, size=110):
    total = sum(s['value'] for s in segments)
    if total == 0: return ''
    cx, cy, r = size/2, size/2, size/2 - 2
    paths = []
    angle = -90 
    for seg in segments:
        if seg['value'] == 0: continue
        sweep = (seg['value'] / total) * 360
        if sweep >= 360: sweep = 359.99
        start_angle = angle
        end_angle = angle + sweep
        x1 = cx + r * math.cos(math.radians(start_angle))
        y1 = cy + r * math.sin(math.radians(start_angle))
        x2 = cx + r * math.cos(math.radians(end_angle))
        y2 = cy + r * math.sin(math.radians(end_angle))
        large_arc = 1 if sweep > 180 else 0
        d = f"M {cx} {cy} L {x1} {y1} A {r} {r} 0 {large_arc} 1 {x2} {y2} Z"
        paths.append(f'<path d="{d}" fill="{seg["color"]}" stroke="var(--paper)" stroke-width="2"/>')
        angle = end_angle
    return f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" class="rec-pie-svg">{"".join(paths)}</svg>'

def _pie_section(title, segments):
    total = sum(s['value'] for s in segments)
    if not segments or total == 0: return ''
    legend_items = ''.join(
        f'<div class="rec-pie-legend-item">'
        f'<span class="rec-pie-dot" style="background:{seg["color"]}"></span>'
        f'<span class="rec-pie-name">{_html.escape(seg["name"] or "—")}</span>'
        f'<span class="rec-pie-pct">{seg["value"] / total * 100:.0f}%</span>'
        f'</div>'
        for seg in segments if seg['value'] > 0
    )
    return (
        f'<div class="rec-breakdown-section rec-breakdown-section--wide">'
        f'<div class="rec-breakdown-title">{title}</div>'
        f'<div class="rec-pie-wrap">'
        f'{_pie_svg(segments)}'
        f'<div class="rec-pie-legend">{legend_items}</div>'
        f'</div>'
        f'</div>'
    )
