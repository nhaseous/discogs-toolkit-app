import collections
import html as _html

from helper import charts
from helper.charts import PIE_COLORS as _PIE_COLORS

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

    # Added-year data: line graph uses year-ascending order; table uses year-descending
    added_year_data  = sorted(added_year_counts.items())                       # [(year, count), ...]
    added_year_table = sorted(added_year_counts.items(), reverse=True)         # [(year, count), ...]

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
        # and the card height = max of all panels (and is stretched to the sibling
        # Format card via the flex row). We toggle with visibility, not display, so
        # panels keep their grid space and stay measurable while hidden.
        #
        # sizeScroll() sizes the Added panel's scroll area in the un-merged (toggle)
        # layout. tryMerge() runs once on load: if the card has enough slack beneath
        # the Year pie, it relocates Added History (subheader + graph + table) under
        # the pie and collapses the card to a 2-state Year+Added <-> Genre toggle.
        'var sizeScroll=function(){'
        'if(wrap._locked)return;'
        'var ap=wrap.querySelector(":scope>[data-panel=\'added\']");'
        'if(!ap)return;'
        'var sc=ap.querySelector(".insights-added-scroll");'
        'if(sc){sc.style.maxHeight="0";sc.style.overflow="hidden";}'
        'var wh=wrap.offsetHeight,th=34,gh=82;'
        'var t=ap.querySelector(".rec-breakdown-title");'
        'var g=ap.querySelector(".insights-line-graph-wrap");'
        'if(t)th=t.offsetHeight+10;'
        'if(g)gh=g.offsetHeight+10;'
        'if(wh>0){'
        'if(sc){sc.style.maxHeight=Math.max(60,wh-th-gh)+"px";sc.style.overflow="";sc.style.overflowY="auto";}'
        'wrap._locked=true;'
        '}'
        '};'
        '(function tryMerge(){'
        'var wrapH=wrap.offsetHeight;'
        'if(wrapH<=0){sizeScroll();return;}'
        'var yearPanel=wrap.querySelector(":scope>[data-panel=\'year\']");'
        'var addedPanel=wrap.querySelector(":scope>[data-panel=\'added\']");'
        'var yPieSvg=yearPanel?yearPanel.querySelector(".rec-pie-wrap svg"):null;'
        'if(!yearPanel||!addedPanel||!yPieSvg){sizeScroll();return;}'
        'var yTitle=yearPanel.querySelector(".rec-breakdown-title");'
        'var yPieWrap=yearPanel.querySelector(".rec-pie-wrap");'
        'var gWrap=addedPanel.querySelector(".insights-line-graph-wrap");'
        'var scrollEl=addedPanel.querySelector(".insights-added-scroll");'
        'var firstRow=scrollEl?scrollEl.querySelector("tr"):null;'
        'var yTitleH=yTitle?yTitle.offsetHeight:34;'
        'var yPieH=yPieWrap?yPieWrap.offsetHeight:0;'
        'var gSvg=gWrap?gWrap.querySelector("[data-vh]"):null;'
'var gVH=gSvg?parseFloat(gSvg.dataset.vh||"106"):106;'
'var fixedH=Math.round(gVH*13/9);'
'var graphH=gWrap?Math.min(gWrap.offsetHeight,fixedH):fixedH;'
        'var rowH=firstRow?firstRow.offsetHeight:30;'
        # Measure the card height with the Added panel pulled OUT of the grid, so the
        # full table no longer dictates the card size. The card then reflects the year
        # pie / genre panel / sibling Format card, and we fit as many rows as fit into
        # the slack (scrolling the rest) instead of growing the card to show every row.
        # graphH/rowH are read above while the panel is still laid out.
        'addedPanel.style.display="none";'
        'var cardH=wrap.offsetHeight;'
        'addedPanel.style.display="";'
        'var available=cardH-yTitleH-yPieH;'
        # HEAD = title's 10px bottom margin + sub-label height (~14px) + sub-label
        # margin-bottom (3px). Sub-label margin-top is `auto` in the flex-column year
        # panel (resolves to 0 at minimum), so it no longer adds to the minimum HEAD.
        'var HEAD=27;'
        # Require room for the subheader + graph. The scroll always shows at least one
        # row (Math.max(rowH,...) below); when the slack is just short of one row the
        # card grows by at most one row height. With more slack we show more rows and
        # the card is unchanged. If even subheader+graph won't fit, growing would be too
        # much — keep the secondary toggle instead.
        'if(available<HEAD+graphH){sizeScroll();return;}'
        'var sub=document.createElement("div");'
        'sub.className="insights-format-sub insights-format-sub--lower";'
        'sub.textContent="Added History";'
        'yearPanel.appendChild(sub);'
        'var body=document.createElement("div");'
        'body.className="insights-added-body";'
        'if(gWrap)body.appendChild(gWrap);'
        'if(scrollEl)body.appendChild(scrollEl);'
        'yearPanel.appendChild(body);'
        'if(addedPanel.parentNode)addedPanel.parentNode.removeChild(addedPanel);'
        'var addedBtn=yearPanel.querySelector(".insights-toggle-switch[data-goto=\'added\']");'
        'if(addedBtn&&addedBtn.parentNode)addedBtn.parentNode.removeChild(addedBtn);'
        # Genre Breakdown stays the default-open panel (server-rendered default); the
        # merged Year+Added panel is reached via its "/ Year" toggle.
        # Clear any inline overflow/maxHeight set by sizeScroll() so the CSS rules
        # for .insights-added-body > .insights-added-scroll take over (max-height and
        # overflow-y are set there to match the fixed graph height).
        'requestAnimationFrame(function(){'
        'if(scrollEl){scrollEl.style.maxHeight="";scrollEl.style.overflow="";scrollEl.style.overflowY="";}'
        '});'
        'wrap._locked=true;wrap._merged=true;'
        '})();'
        'wrap.querySelectorAll(".insights-toggle-switch").forEach(function(btn){'
        'btn.addEventListener("click",function(){'
        'var target=btn.dataset.goto;'
        'sizeScroll();'
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
        return charts.pie_section("Genre Breakdown", genre_pie, filter_field='genres')
    if not has_genre and not has_added:
        return charts.pie_section("Year Breakdown", year_pie, filter_field='decade')

    # ── Panel 1: Year Breakdown ──────────────────────────────────────────────
    year_pie_html = (
        f'<div class="rec-pie-wrap">'
        f'{charts.pie_svg(year_pie, filter_field="decade") if has_year else ""}'
        f'<div class="rec-pie-legend">'
        f'{charts.pie_legend_html(year_pie, filter_field="decade") if has_year else ""}'
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
    line_graph = charts.line_graph_svg(added_year_data) if has_added else ''
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
        f'{charts.pie_svg(genre_pie, filter_field="genres") if has_genre else ""}'
        f'<div class="rec-pie-legend">'
        f'{charts.pie_legend_html(genre_pie, filter_field="genres") if has_genre else ""}'
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
        svg = charts.pie_svg(segments, size=80, extra_class='rec-pie-svg--sm', filter_field=filter_field)
        legend = f'<div class="rec-pie-legend">{charts.pie_legend_html(segments, filter_field)}</div>'
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
        panel_edition = f'<div class="insights-panel" style="visibility:hidden;pointer-events:none">{charts.bar_chart_html(edition_pie, filter_field="format_tags")}</div>'
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
