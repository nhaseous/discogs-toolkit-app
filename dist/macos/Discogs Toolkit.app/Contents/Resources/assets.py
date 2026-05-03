with open('static/discogs-logo.svg') as _f:
    DISCOGS_LOGO_SVG = _f.read().strip()

with open('static/logo.svg') as _f:
    LOGO_SVG = _f.read().strip().replace('<svg ', '<svg class="brand-icon" ', 1)

VINYL_PLACEHOLDER_SVG = (
    '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="50" cy="50" r="46" fill="currentColor"/>'
    '<circle cx="50" cy="50" r="20" fill="var(--rule)"/>'
    '<circle cx="50" cy="50" r="4" fill="currentColor"/>'
    '</svg>'
)

SEARCH_ICON_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>'
)

RATE_LIMIT_NOTICE = (
    '<div class="lookup-notice lookup-notice--error">'
    'Discogs is rate limiting requests right now. '
    'Please wait 60 seconds before you try again.'
    '</div>'
)

BACK_ARROW_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M19 12H5"/><path d="M12 5l-7 7 7 7"/></svg>'
)

EYE_CLOSED_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M3 12Q12 17 21 12"/>'
    '<line x1="3" y1="12" x2="1.5" y2="15"/>'
    '<line x1="7.5" y1="13.8" x2="6.8" y2="17.2"/>'
    '<line x1="12" y1="14.5" x2="12" y2="18"/>'
    '<line x1="16.5" y1="13.8" x2="17.2" y2="17.2"/>'
    '<line x1="21" y1="12" x2="22.5" y2="15"/>'
    '</svg>'
)

EYE_OPEN_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>'
    '<circle cx="12" cy="12" r="3"/>'
    '</svg>'
)
