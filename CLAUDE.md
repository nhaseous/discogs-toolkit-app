# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Discogs Toolkit is a Flask web app for Discogs marketplace research and collection browsing. It has five tools:
- **Price Checker** (`/pricechecker`): scrapes a seller's inventory and shows where each listing ranks among all marketplace listings for the same release. Disabled on GAE (Cloudflare blocks scraping from server IPs); only available locally and in the macOS desktop app. Supports a per-user **Watchlist** persisted to Firestore.
- **Matcher** (`/matcher`): finds overlap between one user's collection and another user's wantlist
- **Lookup** (`/lookup`): browse any user's collection, wantlist, and curated lists as a card grid. Includes an **Insights Dashboard** for collection stats and estimated value.
- **Recommendations** (`/recommend`): builds a taste profile from any user's collection and asks Gemini (Vertex AI) for vinyl records they likely don't own but would love, then resolves each suggestion to a real Discogs release. Includes a "New artists" toggle to restrict suggestions to artists not already in the collection.
- **Records** (`/records`): personal collection dashboard backed by Google Sheets; restricted to user `curefortheitch`

Deployed on Google App Engine. Live at: https://discogs-toolkit.uc.r.appspot.com

Also ships as a standalone macOS desktop app (built with `py2app` + `pywebview`).

## Tech Stack

- **Python/Flask** — web framework; routes are split into Flask blueprints under `routes/` (registered in `main.py` via `register_blueprints`)
- **cloudscraper** — wraps `requests` to bypass Cloudflare on Discogs HTML pages
- **BeautifulSoup4** — parses scraped HTML marketplace pages
- **Discogs REST API** — used directly for collection, wantlist, inventory, list, and search data
- **requests-oauthlib** — OAuth 1.0a flow for Discogs login (`/login` → `/callback`)
- **ThreadPoolExecutor** — concurrent scraping; 10 workers in Price Checker, 5 in Matcher/Lookup/Recommendations
- **google-genai (Vertex AI / Gemini)** — generates the recommendation candidates; authenticates with the same service-account JSON as the Sheets client
- **gspread + google-auth** — Google Sheets access for the Records dashboard
- **Google Cloud Firestore** — persists user watchlists; also backs the per-IP daily and global monthly caps on Recommendations
- **Google App Engine** — production deployment (`app.yaml`, `runtime: python312`)
- **pywebview + pyobjc** — native macOS .app wrapper (macOS only)

## Key Files and Directories

```
main.py               # Flask entry point — app setup, context processor, session config, registers blueprints
web_common.py         # Shared web helpers: app auth (DiscogsAppAuth), oauth_auth(), price-checker gating
assets.py             # Loads SVGs and HTML snippets into module-level constants at startup
mac_main.py           # macOS .app entry point — starts Flask + opens pywebview window
setup.py              # py2app config for building the macOS .app bundle

routes/               # Flask blueprints, one module per tool (registered by routes/__init__.py)
  core_routes.py      # Landing page, favicon, versioned static
  auth_routes.py      # /login, /callback, /logout (OAuth 1.0a)
  pricechecker_routes.py # /pricechecker, /scrape_batch, /reprice, /refresh_card, /watchlist
  matcher_routes.py   # /matcher
  lookup_routes.py    # /lookup + insights/data/load-tab/folders/list sub-routes
  recommend_routes.py # /recommend (shell) + /recommend/batch (one streamed Gemini round)
  records_routes.py   # /records

services/
  clients/            # External API integrations
    discogs_client.py # Discogs REST API: session management, pagination, search, RequestBudget
    google_client.py  # Google Sheets API client (gspread)
    firestore_db.py   # Firestore: watchlist persistence + Recommendations IP/monthly caps
  logic/              # Feature-specific business logic
    lookup.py         # Lookup: collection, wantlist, lists fetch + list page scraping
    matcher.py        # Matcher: collection/wantlist comparison
    pricechecker.py   # Price Checker: inventory fetch, marketplace scraping, HTML rendering
    recommend.py      # Recommendations: taste profile → Gemini candidates → Discogs release resolution
    insights.py       # Aggregates collection stats
    charts.py         # SVG chart generators (pie, bar, line)
  utils/              # Shared helpers and utilities
    auth.py           # macOS Keychain credential persistence (save/get/delete)
    common.py         # Shared API headers (User-Agent)
    lookup_cache.py   # In-memory cache for lookup payloads
    records.py        # Records: Google Sheets load + data parsing
  models/
    models.py         # Shared data structures (FormattedEntry)

server/               # Standalone background monitor (NOT wired into web routes)
  server.py           # PriceCheckerServer — manages Worker threads
  worker.py           # Worker — polls seller inventory, sends Discord webhook on changes

static/
  css/
    vars.css          # Design tokens, reset, global layout — loaded on every page
    sidebar.css       # Left nav sidebar — loaded on every page
    components.css    # Search bar, spinner, badges — loaded on tool pages
    results.css       # Result cards, tabs, pagination, mosaics — loaded on tool pages
    tools.css         # Landing page tool card grid — loaded on / only
  js/
    main.js           # Global UI: sidebar, tabs, pagination, badge filter pills, tooltips
    pricechecker.js   # Price Checker: filter pills, card refresh, reprice modal + API calls
    recommend.js      # Recommendations: streams Gemini rounds from /recommend/batch into the grid
    records.js        # Records dashboard: tab switching between panels

templates/
  base.html           # Master layout: sidebar nav, stylesheet links, content slot, main.js
  macros.html         # Shared Jinja macros (match_card + lookup_grid card grid)
  _recommend_cards.html # Bare match_card list returned by /recommend/batch for client append
  _recommend_lines.html # Per-release text lines for the Recommendations card (same data as cards)
  landing.html        # Tool card grid (extends base)
  pricechecker.html   # Extends base; sets window.TOOLKIT_CONFIG; loads pricechecker.js
  matcher.html        # Extends base
  lookup.html         # Extends base
  recommend.html      # Extends base; "New artists" toggle, streaming shell, loads recommend.js
  records.html        # Extends base; loads records.js
```

## Routes

| Route | Method | Purpose | Auth |
|---|---|---|---|
| `/` | GET | Landing page with tool cards | — |
| `/login` | GET | Start OAuth1 flow — redirects to Discogs | — |
| `/callback` | GET | OAuth1 callback — saves tokens to session (+ Keychain on macOS) | — |
| `/logout` | GET | Clears session and Keychain entry | — |
| `/pricechecker` | GET | Price Checker UI (disabled on GAE) | Optional |
| `/scrape_batch` | POST | JSON API — scrapes a batch of release cards for Price Checker | Optional |
| `/matcher` | GET | Matcher UI | Optional |
| `/lookup` | GET | Lookup UI | Optional |
| `/lookup/list` | GET | JSON API — fetches list releases (bypass scrape on GAE) | — |
| `/lookup/insights`, `/lookup/data`, `/lookup/load-tab`, `/lookup/folders` | GET/POST | JSON APIs — Insights dashboard, lazy tab/folder loading | Optional |
| `/recommend` | GET | Recommendations UI shell — cards stream in client-side (`new_artists` toggle) | Optional |
| `/recommend/batch` | POST | JSON API — runs one Gemini round, returns rendered cards + bio; streamed by `recommend.js` | Optional |
| `/watchlist` | GET/POST | Firestore API — manage user's Price Checker watchlist | Required |
| `/records` | GET | Personal records dashboard | `curefortheitch` only |
| `/reprice` | POST | JSON API — reprices selected Discogs listings | Required |
| `/refresh_card` | POST | JSON API — re-scrapes a single release card | Optional |

## Commands

```bash
# Run dev server (http://127.0.0.1:8080)
python main.py

# Install dependencies
pip install -r requirements.txt

# Deploy to Google App Engine
gcloud app deploy

# Build macOS .app
python3 setup.py py2app
```

No test suite exists.

## Authentication (OAuth 1.0a)

Discogs uses OAuth 1.0a. Credentials are stored in `app.yaml` env vars:
- `DISCOGS_CONSUMER_KEY` / `DISCOGS_CONSUMER_SECRET`
- `DISCOGS_CALLBACK_URL` — differs between GAE and localhost
- `FLASK_SECRET_KEY` — Flask session signing

On a successful `/callback`, tokens are written to the Flask session. On macOS, they're also persisted to Keychain via `services/utils/auth.py` so the user stays logged in across app restarts. A `before_request` hook (`_load_persistent_auth`) restores Keychain credentials into the session on each request if the session is empty.

Price Checker is gated by `_is_price_checker_enabled()`: returns True only on localhost or when running as a frozen macOS app.

## APIs

**Base URL:** `https://api.discogs.com`  
**Docs:** https://www.discogs.com/developers

The calls this app makes access public user data, but the app authenticates *every* request anyway to earn the higher rate-limit tier. Signed-in users authenticate as themselves via OAuth; signed-out users authenticate at the **application level** using the consumer key/secret (`DiscogsAppAuth` in `web_common.py`, sent as `Authorization: Discogs key=…, secret=…`). App auth carries no user identity (it can't read private data or write) but still lifts requests from the unauthenticated tier to the authenticated one. Per the [Discogs API rate-limiting docs](https://www.discogs.com/developers/accessing.html#page:home,header:home-rate-limiting), Discogs throttles per source IP over a sliding 60-second window: unauthenticated requests are capped at **25/minute**, authenticated requests (OAuth *or* app auth) at **60/minute**. The `X-Discogs-Ratelimit-Remaining` response header can be read to throttle proactively before hitting HTTP 429.

### REST API endpoints in use

| Endpoint | Used in | Notes |
|---|---|---|
| `GET /users/{username}/inventory` | `pricechecker.py` | Returns seller's for-sale listings. Paginated. |
| `GET /users/{username}/collection/folders/0/releases` | `lookup.py`, `matcher.py` | Folder `0` is the "All" folder. Also feeds the Recommendations taste profile. |
| `GET /users/{username}/collection/value` | `discogs_client.py` | Fetches collection value range. Requires auth for owner. |
| `GET /users/{username}/wants` | `lookup.py`, `matcher.py` | Returns user's wantlist. |
| `GET /users/{username}/lists` | `lookup.py` | Returns the user's curated lists index. |
| `GET /database/search` | `recommend.py` | Resolves a Gemini suggestion to a real Vinyl (non-Unofficial) release; tries a strict then a free-text query. |
| `GET /listings/{listing_id}` | `pricechecker_routes.py` `/reprice` | Fetches current listing data before updating. |
| `POST /listings/{listing_id}` | `pricechecker_routes.py` `/reprice` | Updates a listing's price (requires OAuth). |

### HTML scraping endpoints in use

These use `cloudscraper` + BeautifulSoup rather than the REST API:

| URL | Used in | Notes |
|---|---|---|
| `https://www.discogs.com/sell/release/{release_id}` | `pricechecker.py` | Marketplace listings page; parses the `mpitems` table for pricing. |
| `https://www.discogs.com/lists/{list_id}` | `lookup.py` | List detail page; parses the embedded `<script id="dsdata">` Apollo cache JSON for items, thumbnails, and per-item comments. Paginated via `?page=N`. |

### Recommendations (Vertex AI / Gemini)

`services/logic/recommend.py` runs a three-stage pipeline:

1. **Taste profile** — reuses the Insights aggregation (`insights.py`) to turn the collection into a compact text summary of top genres/styles/artists/labels/decades. No extra Discogs calls beyond the collection fetch.
2. **Gemini candidates** — calls Gemini via Vertex AI (`google-genai`, model `gemini-2.5-flash` by default) using **structured output** (`response_schema`) so it returns validated JSON, not a delimited text format. Returns a 2-sentence taste **bio** plus the candidates; the bio is requested only on the first round (`want_bio`), since later rounds discard it. Authenticates with the same service-account JSON as the Sheets client (`GOOGLE_SA_KEY_B64` / `GOOGLE_APPLICATION_CREDENTIALS`).
3. **Resolution** — each suggestion is resolved to a real Discogs release via `/database/search`, requiring a Vinyl, non-Unofficial result that fuzzy-matches the artist/album (token-coverage match). Tries a strict structured query, then a looser free-text query.

**Streaming delivery** — the Gemini call dominates latency (~15–22s/round), so `/recommend` renders only the page shell and `recommend.js` streams rounds in one at a time via `POST /recommend/batch`. Each call runs one `run_recommendation_round` (5 candidates for the initial streaming rounds; manual "get more" refreshes over-ask for `_REFRESH_CANDIDATES`=10, since ~half are lost to the owned filter or to candidates with no qualifying Discogs vinyl release) and returns rendered cards; the first batch (with the bio) paints as soon as one round resolves, and later rounds append under a "Finding more…" footer until ~10 releases or the 3-round cap. The endpoint is stateless across rounds — the client round-trips `considered` (already-suggested `{artist, album}` pairs) and `seen_ids` (rendered release IDs) to avoid repeats. The viewed user's collection is fetched once and cached in `lookup_cache` under a shared key (`("collection", username)`) — also written by the Lookup tool, so a Lookup→Recommend flow reuses the same collection instead of re-paging it. The built taste profile is cached alongside the items (and passed into each `run_recommendation_round`) so it isn't re-aggregated per round. Resolved `/database/search` results are memoized in a long-TTL in-memory cache (`recommend._search_cache`, keyed by normalized artist|album) — popular candidates recur across collectors, and a cache hit issues no Discogs request and spends no request budget; only positive matches are cached (a `None` may mean budget exhaustion, not "no release"). `get_recommendation_cards` loops the same per-round core as an all-at-once, non-streaming variant targeting the same 10-result goal, but it is not wired to any live route — the streaming path is the only one in use.

Cost/abuse guards (all in `firestore_db`): a **per-IP daily round cap** (`RECOMMEND_IP_DAILY_ROUND_LIMIT`, default 50) consumed per Gemini round — so a full 3-round search uses ~3 of the day's allowance (≈16 searches/day); a mid-search cap hit keeps the cards already found, only a round-0 hit shows the notice — and a **global monthly Gemini-round cap** (`RECOMMEND_MONTHLY_ROUND_CAP`, default 1000) consumed per Gemini round. Signed-out requests budget each round's burst with a `RequestBudget(60)`. Relevant env vars: `VERTEX_GEMINI_MODEL`, `VERTEX_LOCATION`, `VERTEX_THINKING_BUDGET`, `RECOMMEND_IP_DAILY_ROUND_LIMIT`, `RECOMMEND_MONTHLY_ROUND_CAP`, `GCP_PROJECT`.

**Cost (measured, for tuning):** $0.73 / 121 rounds ≈ **$0.0060/round** (~0.60¢), at ~2,000 input + ~2,000 output-billed tokens/round (the `VERTEX_THINKING_BUDGET`=128 thinking tokens bill as output) against `gemini-2.5-flash` list pricing (~$0.30/1M in, ~$2.50/1M out — output is ~90% and scales with candidate count, not round count). So ~3-round search ≈ $0.018, the 50/day IP cap ≈ $0.30/day/IP, and the 1000/month global cap ≈ **$6.00/month** effective spend ceiling. Round usage lives in Firestore (`usage/gemini_rounds_<YYYY-MM>` global, `ratelimit/<ip>_<YYYY-MM-DD>` per-IP). Full knob table and budget→cap formula in [README](README.md#tuning--cost); re-derive $/round if the model, thinking budget, or `_TARGET_RESULTS` changes.

## Additional Documentation

- [Architectural Patterns](.claude/docs/architectural_patterns.md) — HTML-as-strings rendering, scraping patterns, data flow
