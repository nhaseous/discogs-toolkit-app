# Architectural Patterns

## HTML generated as Python strings (no template engine)

The entire UI is built by concatenating string literals — there is no Jinja2 or other template engine. `page_layout()` in `main.py:30` wraps every page with the nav, stylesheet links, and all inline JavaScript. Route handlers (`pricecheckerpage`, `matcherpage`) build their content as a string and pass it in.

The `FormattedEntry.__str__` method in `services/logic/pricechecker.py:29` returns an HTML fragment, which means the data model doubles as a view component. Calling `str(entry)` (or interpolating it into an f-string) emits the card HTML directly.

## All JavaScript is inlined as string literals

There is no separate JS file. All client-side behavior — filter pills, sticky mosaic, badge tooltips, form submit animations, sidebar art animations — is a single large string concatenated at the end of `page_layout()` (`main.py:77–346`). When adding or modifying interactive behavior, edit that string block.

## Two distinct data sources, two scraping strategies

- **Price Checker** (`services/logic/pricechecker.py`): Uses the Discogs REST API to get a seller's inventory (`get_inventory_ids`), then **scrapes Discogs HTML marketplace pages** with BeautifulSoup for per-release listing data (`get_listings`). The HTML scraping is necessary because the listing details (competitor prices, seller ratings) aren't available via the public API.

- **Matcher** (`services/logic/matcher.py`): Uses the **Discogs REST API exclusively** — no HTML scraping. `_fetch_all_pages` handles pagination generically for both collection and wantlist endpoints.

## `cloudscraper` used everywhere instead of `requests`

All HTTP calls go through a `cloudscraper` instance (created per-request in each route handler). This bypasses Cloudflare's bot protection on marketplace HTML pages. The same scraper instance is passed through to helper functions rather than created inside them (`services/logic/pricechecker.py:84`, `services/logic/matcher.py:15`).

## ThreadPoolExecutor for concurrent per-release scraping

Price Checker fires one `get_listings` call per release in the seller's inventory, all concurrently with `max_workers=10` (`main.py:410`). Results are written into a pre-allocated list (`inventory_list = [None] * len(release_titles_ids)`) using the release's index as the slot — a threading-safe pattern because each thread writes to a distinct index. A `threading.Lock` (`_list_lock`) guards writes to `sorted_inventory_list` since multiple threads could append to the same bucket (`services/logic/pricechecker.py:7`, `176`).

## Routes are synchronous; all work happens in the request thread

There's no background job queue or async handling. When a user submits a search, the Flask route blocks until all scraping finishes, then returns the full HTML page. The `server/` module (standalone worker + Discord notifications) is entirely separate from the web app and is not invoked by any route.

## Badge filtering is purely client-side

Result cards are rendered with `data-badges="..."` attributes (`services/logic/pricechecker.py:237`). The filter pills in the UI toggle `display: none` on cards by reading those attributes — no server round-trip. The badge values (`recent`, `old`, `low`, `lowest`, `high`, `highest`) are computed by `_entry_badges()` at render time (`services/logic/pricechecker.py:205`).
