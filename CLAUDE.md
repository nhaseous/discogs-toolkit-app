# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Discogs Toolkit is a Flask web app for Discogs marketplace research and collection browsing. It has five tools:
- **Price Checker** (`/pricechecker`): scrapes a seller's inventory and shows where each listing ranks among all marketplace listings for the same release. Disabled on GAE (Cloudflare blocks scraping from server IPs); only available locally and in the macOS desktop app. Supports a per-user **Watchlist** persisted to Firestore.
- **Matcher** (`/matcher`): finds overlap between one user's collection and another user's wantlist
- **Lookup** (`/lookup`): browse any user's collection, wantlist, and curated lists as a card grid. Includes an **Insights Dashboard** for collection stats and estimated value, and an in-app **music preview player**: each card gets a play button that resolves the release to an Apple Music album (via the keyless iTunes Search API) and streams previews through Apple's native embed in a fixed right rail.
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
- **Google Secret Manager** — holds secrets on GAE (`FLASK_SECRET_KEY`, Discogs consumer key/secret, `GOOGLE_SA_KEY_B64`); hydrated into `os.environ` at startup by `services/clients/secrets.py`. Local dev and the macOS app use `.env`/Keychain instead.
- **iTunes Search API** — keyless public API used by the Lookup preview player to resolve releases to Apple Music albums (`services/logic/player.py`)
- **Google App Engine** — production deployment (`app.yaml`, `runtime: python312`)
- **pywebview + pyobjc** — native macOS .app wrapper (macOS only)

## Key Files and Directories

```
main.py               # Flask entry point — loads secrets first, then app setup, context processor, session config, blueprints
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
  player_routes.py    # /player/resolve — Discogs release → Apple Music album (JSON)

services/
  clients/            # External API integrations
    discogs_client.py # Discogs REST API: session management, pagination, search, RequestBudget
    google_client.py  # Google Sheets API client (gspread)
    firestore_db.py   # Firestore: watchlist persistence + Recommendations IP/monthly caps
    secrets.py        # Loads secrets from Google Secret Manager into os.environ (GAE only; no-op locally)
  logic/              # Feature-specific business logic
    lookup.py         # Lookup: collection, wantlist, lists fetch + list page scraping
    matcher.py        # Matcher: collection/wantlist comparison
    pricechecker.py   # Price Checker: inventory fetch, marketplace scraping, HTML rendering
    recommend.py      # Recommendations: taste profile → Gemini candidates → Discogs release resolution
    insights.py       # Aggregates collection stats
    charts.py         # SVG chart generators (pie, bar, line)
    player.py         # Preview player: iTunes Search API resolution + fuzzy match + 24h cache
  utils/              # Shared helpers and utilities
    auth.py           # macOS Keychain credential persistence (save/get/delete)
    common.py         # Shared API headers (User-Agent)
    ttl_cache.py      # Generic thread-safe TTL cache (backs lookup_cache, recommend search cache, player cache)
    lookup_cache.py   # In-memory cache for lookup payloads (shared with Recommendations)
    records.py        # Records: Google Sheets load + data parsing
  models/
    models.py         # Shared data structures (FormattedEntry)

server/               # Standalone background monitor (NOT wired into web routes)
  server.py           # PriceCheckerServer — manages Worker threads
  worker.py           # Worker — polls seller inventory, sends Discord webhook on changes

static/
  css/
    vars.css          # Variables and reset — loaded on every page
    main.css          # Global layout, typography, shared patterns — loaded on every page
    sidebar.css       # Left nav sidebar — loaded on every page
    components.css    # Search bar, spinner, meta, badges — tool pages
    results.css       # Lookup search/header, shared tabs + pagination, dashboard base (.rec-*)
    cards.css         # Result cards (Price Checker) + match cards (Matcher, Lookup)
    mosaic.css        # Thumbnail mosaics (Price Checker, Matcher, Lookup)
    insights.css      # Insights Dashboard layout, charts, slice/row interactivity
    lookup.css        # Lookup notices and active-filter badges
    player.css        # Preview player rail + play buttons (Lookup only)
    reprice.css       # Reprice modal UI
    records.css       # Records table UI (tabs, toolbar, table, badges)
    tools.css         # Landing page hero + tool card grid — / only
  js/
    main.js           # Global UI: sidebar, tabs, pagination, badge filter pills, tooltips
    utils.js          # Shared DOM/scroll/format helpers
    app-client.js     # Consolidated client for app API calls + centralized error handling
    grid.js           # Shared card-grid behavior (responsive layout, hover) — Matcher + Lookup
    mosaic.js         # Shared mosaic UI — Price Checker + Lookup
    pricechecker.js   # Price Checker: filter pills, card refresh + API calls
    reprice.js        # Reprice modal + API calls
    matcher.js        # Matcher "Exact match" toggle
    lookup.js         # Lookup search-form transition
    lookup-browse.js  # Lookup orchestration: tab/mosaic switching, expand-all toggle
    lookup-filters.js # Lookup per-tab filter state + badge UI
    lookup-pagination.js # Lookup pagination, deferred-load + lazy hydration, page controls
    insights.js       # Insights Dashboard panel toggles
    player.js         # Preview player: play buttons → /player/resolve → Apple embed in right rail
    recommend.js      # Recommendations: streams Gemini rounds from /recommend/batch into the grid
    records.js        # Records dashboard: tab switching between panels

templates/
  base.html           # Master layout: sidebar nav, stylesheet links, content slot, player rail (when show_player), main.js
  macros.html         # Shared Jinja macros (match_card + lookup_grid card grid)
  _recommend_cards.html # Bare match_card list returned by /recommend/batch for client append
  _recommend_lines.html # Per-release text lines for the Recommendations card (same data as cards)
  _insights_fragment.html # Insights Dashboard fragment rendered by /lookup/insights
  landing.html        # Tool card grid (extends base)
  pricechecker.html   # Extends base; sets window.TOOLKIT_CONFIG; loads pricechecker.js
  pricechecker_results.html # Results area shell (mosaic, badge counts) included by pricechecker.html
  matcher.html        # Extends base
  lookup.html         # Extends base; loads lookup*.js, player.js, insights.js
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
| `/player/resolve` | POST | JSON API — resolves a release (artist + title) to an Apple Music album for the Lookup preview player | — |
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

## Secrets and Configuration

Secrets (`FLASK_SECRET_KEY`, `DISCOGS_CONSUMER_KEY`, `DISCOGS_CONSUMER_SECRET`, `GOOGLE_SA_KEY_B64`) live in **Google Secret Manager** (secret IDs match the env var names one-to-one). `main.py` calls `services/clients/secrets.load_secrets()` before any other module reads the environment; on GAE it hydrates `os.environ` via the runtime service account, so the rest of the app keeps using `os.environ.get` unchanged. Off App Engine it's a no-op — local dev reads `.env` (via `python-dotenv`) and the macOS app uses Keychain; set `USE_SECRET_MANAGER=1` to opt a local run in (requires ADC). Values already present in the environment are never overwritten. Non-secret config (`DISCOGS_CALLBACK_URL`, `VERTEX_LOCATION`, `VERTEX_GEMINI_MODEL`) stays in `app.yaml`.

## Authentication (OAuth 1.0a)

Discogs uses OAuth 1.0a using the consumer key/secret above; `DISCOGS_CALLBACK_URL` differs between GAE and localhost.

On a successful `/callback`, tokens are written to the Flask session. On macOS, they're also persisted to Keychain via `services/utils/auth.py` so the user stays logged in across app restarts. A `before_request` hook (`_load_persistent_auth`) restores Keychain credentials into the session on each request if the session is empty.

Price Checker is gated by `web_common.is_price_checker_enabled()`: returns True only on localhost or when running as a frozen macOS app.

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

### Music preview player (iTunes Search API)

`services/logic/player.py` resolves a Discogs release (artist + album title) to an Apple Music album for the Lookup page's in-app preview player. It uses the public **iTunes Search API** (`https://itunes.apple.com/search` and `/lookup`) — no API key, no OAuth — so it works identically on GAE, local dev, and the macOS build, and spends no Discogs request budget. Resolution tries progressively broader strategies: an album search, then a song search (rescues albums iTunes mis-tags at the album level — each song result carries its album's id/artwork), then a discography scan via `/lookup` on the resolved artist id (rescues catalog albums `/search`'s relevance ranking omits). Every candidate must pass a fuzzy token-coverage match against the iTunes `artistName`/`collectionName` fields before acceptance. Positive resolutions are memoized for 24h in a `TTLCache` (only successes — a miss may be a transient network failure). The returned `collectionId` drives Apple's native embed player (`embed.music.apple.com`), which streams ~30–90s previews for anonymous visitors (full playback for signed-in Apple Music subscribers). Client side, `player.js` injects play buttons on Lookup cards, calls `POST /player/resolve`, and loads the embed into the fixed right rail (`#player-rail` in `base.html`, rendered when `show_player` is set); the resolved album cover slides in over the sidebar's spinning platter.

### Recommendations (Vertex AI / Gemini)

`services/logic/recommend.py` runs a three-stage pipeline:

1. **Taste profile** — reuses the Insights aggregation (`insights.py`) to turn the collection into a compact text summary of top genres/styles/artists/labels/decades. `build_recommendation_profile` renders **two variants** from one aggregation, differing only in their "Top artists" line: a default profile listing the top `_NORMAL_ARTIST_CAP` (15) artists, and a "new artists" profile listing the top `_PROFILE_ARTIST_CAP` (default 100; env `RECOMMEND_PROFILE_ARTIST_CAP`). The mode determines which is used. In **normal mode** the artist list is only a taste signal — recommendations may include new releases by artists the collector already owns, so there is no artist-level avoidance (only the album-level owned filter drops exact owned albums). To cut the main normal-mode non-hit (Gemini re-suggesting an album the collector already has), the default profile also appends an **owned-album block** (`_owned_albums_block`): the owned album *titles* of the most-collected artists, grouped by artist and capped (`_OWNED_ALBUM_ARTISTS`/`_OWNED_ALBUM_PER_ARTIST`/`_OWNED_ALBUM_MAX_TITLES`), with an instruction not to re-suggest those specific records — which still leaves Gemini free to suggest *other, unowned* albums by the same artists. It's omitted from the new-artists profile (those artists are excluded wholesale there). In **new-artists mode** the 100-artist list doubles as the **owned-artist avoidance set**: the prompt marks those artists as already-owned and tells Gemini to skip them, and for collections with more owned artists than the cap each round also appends a rotating random sample (`_OWNED_EXCLUDE_SAMPLE`, default 40) of the remaining owned artists so the long tail is covered without re-listing everyone. Both profile variants plus the full ranked owned-artist list are cached (so toggling the mode doesn't re-aggregate); `build_taste_profile` is a thin wrapper returning the default variant's text. No extra Discogs calls beyond the collection fetch.
2. **Gemini candidates** — calls Gemini via Vertex AI (`google-genai`, model `gemini-2.5-flash` by default) using **structured output** (`response_schema`) so it returns validated JSON, not a delimited text format. Returns a 2-sentence taste **bio** plus the candidates; the bio is requested only on the first round (`want_bio`), since later rounds discard it. Authenticates with the same service-account JSON as the Sheets client (`GOOGLE_SA_KEY_B64` / `GOOGLE_APPLICATION_CREDENTIALS`).
3. **Resolution** — each suggestion is resolved to a real Discogs release via `/database/search`, requiring a Vinyl, non-Unofficial result that fuzzy-matches the artist/album (token-coverage match). Tries a strict structured query, then a looser free-text query.

**Streaming delivery** — the Gemini call dominates latency (~15–22s/round), so `/recommend` renders only the page shell and `recommend.js` streams rounds in one at a time via `POST /recommend/batch`. Each call runs one `run_recommendation_round` (5 candidates for the initial streaming rounds; manual "get more" refreshes over-ask for `_REFRESH_CANDIDATES`=10, since ~half are lost to the owned filter or to candidates with no qualifying Discogs vinyl release) and returns rendered cards; the first batch (with the bio) paints as soon as one round resolves, and later rounds append under a "Finding more…" footer until ~10 releases or the 3-round cap. The endpoint is stateless across rounds — the client round-trips `considered` (already-suggested `{artist, album}` pairs) and `seen_ids` (rendered release IDs) to avoid repeats. The viewed user's collection is fetched once and cached in `lookup_cache` under a shared key (`("collection", username)`) — also written by the Lookup tool, so a Lookup→Recommend flow reuses the same collection instead of re-paging it. The built taste profile and ranked owned-artist list are cached alongside the items (and passed into each `run_recommendation_round`) so they aren't re-aggregated per round. Resolved `/database/search` results are memoized in a long-TTL in-memory cache (`recommend._search_cache`, keyed by normalized artist|album) — popular candidates recur across collectors, and a cache hit issues no Discogs request and spends no request budget; only positive matches are cached (a `None` may mean budget exhaustion, not "no release"). `get_recommendation_cards` loops the same per-round core as an all-at-once, non-streaming variant targeting the same 10-result goal, but it is not wired to any live route — the streaming path is the only one in use.

Cost/abuse guards (all in `firestore_db`): a **per-IP daily round cap** (`RECOMMEND_IP_DAILY_ROUND_LIMIT`, default 50) consumed per Gemini round — so a full 3-round search uses ~3 of the day's allowance (≈16 searches/day); a mid-search cap hit keeps the cards already found, only a round-0 hit shows the notice — and a **global monthly Gemini-round cap** (`RECOMMEND_MONTHLY_ROUND_CAP`, default 1000) consumed per Gemini round. Signed-out requests budget each round's burst with a `RequestBudget(60)`. Relevant env vars: `VERTEX_GEMINI_MODEL`, `VERTEX_LOCATION`, `VERTEX_THINKING_BUDGET`, `RECOMMEND_IP_DAILY_ROUND_LIMIT`, `RECOMMEND_MONTHLY_ROUND_CAP`, `GCP_PROJECT`.

**Cost (measured, for tuning):** $0.73 / 121 rounds ≈ **$0.0060/round** (~0.60¢), at ~2,000 input + ~2,000 output-billed tokens/round (the `VERTEX_THINKING_BUDGET`=128 thinking tokens bill as output) against `gemini-2.5-flash` list pricing (~$0.30/1M in, ~$2.50/1M out — output is ~90% and scales with candidate count, not round count). So ~3-round search ≈ $0.018, the 50/day IP cap ≈ $0.30/day/IP, and the 1000/month global cap ≈ **$6.00/month** effective spend ceiling. Round usage lives in Firestore (`usage/gemini_rounds_<YYYY-MM>` global, `ratelimit/<ip>_<YYYY-MM-DD>` per-IP). Full knob table and budget→cap formula in [README](README.md#tuning--cost); re-derive $/round if the model, thinking budget, or `_TARGET_RESULTS` changes.

## Additional Documentation

- [Architectural Patterns](.claude/docs/architectural_patterns.md) — HTML-as-strings rendering, scraping patterns, data flow
