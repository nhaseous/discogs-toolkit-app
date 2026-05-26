import collections

from services.logic.charts import PIE_COLORS as _PIE_COLORS

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
        'total_added':      sum(c for _, c in added_year_table),
        'total_value': total_value,
    }
