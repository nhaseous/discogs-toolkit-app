"""Shared SVG/HTML chart renderers used by the Records and Insights dashboards.

Each renderer takes a list of `segments`, where a segment is a dict with at least
`name`, `value`, and `color`. Color palettes live with each caller (the Records and
Insights dashboards use different palettes), so only the rendering lives here.

`pie_svg`/`pie_section` are parameterized so both call sites reproduce their original
output exactly: the Insights dashboard uses the defaults (110px viewBox, --paper
stroke, interactive `rec-pie-path` slices), while Records passes the larger viewBox,
--bg stroke, and no slice class it has always used.
"""

import html as _html
import math

# Shared categorical palette for all dashboard pies/bars. Callers index into this
# with `PIE_COLORS[i % len(PIE_COLORS)]` (optionally with an offset) to color segments.
PIE_COLORS = [
    '#e11d48', '#d97706', '#059669', '#2563eb', '#7c3aed',
    '#db2777', '#4b5563', '#ea580c', '#65a30d', '#0891b2',
]


def pie_svg(segments, size=110, radius=None, extra_class='', filter_field='',
            path_class='rec-pie-path', stroke='var(--paper)'):
    """Render a pie chart as an inline SVG.

    radius defaults to `size/2 - 2`. filter_field, when set, marks each slice as an
    interactive `insights-filter-row` carrying data-filter-field/value attributes.
    """
    total = sum(s['value'] for s in segments)
    if not segments or total == 0:
        return ''
    cx, cy = size / 2, size / 2
    r = radius if radius is not None else size / 2 - 2
    paths = []
    angle = -90
    for seg in segments:
        if seg['value'] <= 0:
            continue
        sweep = (seg['value'] / total) * 360
        if sweep >= 360:
            sweep = 359.99
        end_angle = angle + sweep
        x1 = cx + r * math.cos(math.radians(angle))
        y1 = cy + r * math.sin(math.radians(angle))
        x2 = cx + r * math.cos(math.radians(end_angle))
        y2 = cy + r * math.sin(math.radians(end_angle))
        large_arc = 1 if sweep > 180 else 0
        d = f"M {cx} {cy} L {x1} {y1} A {r} {r} 0 {large_arc} 1 {x2} {y2} Z"
        classes = []
        if path_class:
            classes.append(path_class)
        ff = ''
        if filter_field:
            classes.append('insights-filter-row')
            ff = (f' data-filter-field="{_html.escape(filter_field)}"'
                  f' data-filter-value="{_html.escape(str(seg["name"] or ""))}"')
        cls_attr = f' class="{" ".join(classes)}"' if classes else ''
        paths.append(
            f'<path{cls_attr} d="{d}" fill="{seg["color"]}" '
            f'stroke="{stroke}" stroke-width="2"{ff}/>'
        )
        angle = end_angle
    svg_cls = f'rec-pie-svg{" " + extra_class if extra_class else ""}'
    return (
        f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" '
        f'class="{svg_cls}">{"".join(paths)}</svg>'
    )


def pie_legend_html(segments, filter_field=''):
    total = sum(s['value'] for s in segments)
    if total == 0:
        return ''
    items = []
    for seg in segments:
        if seg['value'] <= 0:
            continue
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


def pie_section(title, segments, filter_field='', **svg_kwargs):
    """A titled breakdown section pairing a pie chart with its legend.

    Extra keyword args (size, radius, stroke, path_class, extra_class) pass through
    to `pie_svg`, letting the Records dashboard reproduce its larger --bg-stroked pie.
    """
    if not segments or sum(s['value'] for s in segments) == 0:
        return ''
    return (
        '<div class="rec-breakdown-section">'
        f'<div class="rec-breakdown-title">{title}</div>'
        '<div class="rec-pie-wrap">'
        f'{pie_svg(segments, filter_field=filter_field, **svg_kwargs)}'
        f'<div class="rec-pie-legend">{pie_legend_html(segments, filter_field)}</div>'
        '</div>'
        '</div>'
    )


def bar_chart_html(segments, filter_field=''):
    if not segments:
        return ''
    max_val = max((s['value'] for s in segments if s['value'] > 0), default=0)
    if max_val == 0:
        return ''
    rows = []
    for seg in segments:
        if seg['value'] <= 0:
            continue
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


def line_graph_svg(year_data):
    """SVG line graph for added-year history. year_data: [(year, count), ...] sorted ascending."""
    if not year_data:
        return ''
    years  = [d[0] for d in year_data]
    counts = [d[1] for d in year_data]
    n = len(years)
    raw_max = max(counts) if counts else 1

    # Always render the SAME number of evenly-spaced y labels and size the step to fit.
    # Pick the "nice" integer step whose top gridline (intervals × step) sits closest to
    # the max, choosing among a fairly fine ladder of round steps so the fit stays tight.
    # When the chosen top rounds just below the max (e.g. 1047 → top 1000) the line pokes
    # slightly above it; POKE_WEIGHT biases the choice toward covering the max so those
    # pokes stay small rather than letting the line shoot well past the top gridline.
    NUM_LABELS    = 5
    NUM_INTERVALS = NUM_LABELS - 1
    POKE_WEIGHT   = 1.6
    _CANDS = (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8)

    if raw_max <= 0:
        nice_step = 1
    else:
        _ideal = raw_max / NUM_INTERVALS
        _mag   = 10 ** max(0, math.floor(math.log10(_ideal)))
        # integer "nice" steps spanning a few magnitudes around the ideal step
        _steps = sorted({int(b * m) for m in (_mag // 10 or 1, _mag, _mag * 10)
                         for b in _CANDS if float(b * m).is_integer() and b * m >= 1})

        def _cost(s):
            top = s * NUM_INTERVALS
            return (raw_max - top) * POKE_WEIGHT if top < raw_max else (top - raw_max)

        nice_step = min(_steps, key=_cost)

    nice_top = nice_step * NUM_INTERVALS
    y_label_vals = [nice_step * k for k in range(NUM_INTERVALS, -1, -1)]
    # Scale by the larger of the two so the peak reaches the top of the plot and pokes
    # above the top gridline whenever nice_top rounded down below raw_max.
    max_count = max(raw_max, nice_top)

    # Chart height is driven by label count: each y-axis label gets ROW_H px.
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
