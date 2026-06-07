# discogs-toolkit-app

Flask web app for Discogs marketplace research and collection browsing. Deployed on Google App Engine.

**Live:** https://discogs-toolkit.uc.r.appspot.com

---

## Tools

### Price Checker (`/pricechecker`)
Enter a seller's username. Fetches their entire for-sale inventory, then for each release scrapes the Discogs marketplace to show where the seller's listing ranks among all other listings for that release. Each card shows the full list of competing prices with conditions, the seller's rank, total number of marketplace listings, and last sold date. Cards can be filtered by supply (Lowest / Low / High / Highest) and recency (Recent / Old). Logged-in users can reprice selected listings directly from the UI.

**Watchlist:** Logged-in users can add releases to a personal watchlist when viewing their own store. Watchlist state is persisted to Google Cloud Firestore and syncs across devices.

> Price Checker is disabled on Google App Engine (Cloudflare blocks scraping from server IPs). It's available locally and in the macOS desktop app.

### Matcher (`/matcher`)
Enter two usernames — one collection, one wantlist. Returns all releases in the collection that also appear on the wantlist. Two match modes: fuzzy (artist + title + format only) and exact (also includes format description and pressing text). Useful for figuring out what you have that someone else wants, or vice versa.

### User Lookup (`/lookup`)
Enter any Discogs username. Browse their full collection, wantlist, and any public curated lists as a card grid with album art.

**Insights Dashboard:** Aggregates collection and wantlist data into an interactive dashboard showing breakdowns by genre, artist, label, format, and decade. If you look up your own username while logged in, it also displays your total collection value (minimum, median, maximum) and an approximated "Value per Genre" breakdown.

### Recommendations (`/recommend`)
Enter any Discogs username. Builds a taste profile from their collection (top genres, styles, artists, labels, and decades) and asks Gemini, via Google's Vertex AI, for vinyl records they likely don't own but would love. Each suggestion is resolved to a real Discogs release (Vinyl, non-bootleg) and shown as a card with album art and a one-line reason grounded in the profile. A **"New artists"** toggle restricts results to artists not already in the collection — pure discovery rather than new albums by familiar names.

> Recommendations are guarded by a per-IP daily limit and a global monthly Gemini-usage cap to keep costs bounded.

### Records (`/records`)
Personal collection dashboard backed by Google Sheets. Shows collection stats, inventory, and sold records. Restricted to a single user.

---

## Project Structure

```
main.py               # Flask app — setup, context processor, session config, registers blueprints
web_common.py         # Shared web helpers: Discogs app auth, oauth_auth(), price-checker gating
assets.py             # SVG and HTML snippet constants loaded at startup
mac_main.py           # macOS .app entry point
setup.py              # py2app build config for macOS .app

routes/               # Flask blueprints, one per tool (registered in routes/__init__.py)
  core_routes.py      # Landing page, favicon, versioned static
  auth_routes.py      # /login, /callback, /logout
  pricechecker_routes.py # /pricechecker, /scrape_batch, /reprice, /refresh_card, /watchlist
  matcher_routes.py   # /matcher
  lookup_routes.py    # /lookup + insights/data/load-tab/folders/list sub-routes
  recommend_routes.py # /recommend
  records_routes.py   # /records

services/
  clients/            # External API integrations
    discogs_client.py # Discogs REST: retries, pagination, search, RequestBudget rate-limiting
    google_client.py  # Google Sheets client (gspread)
    firestore_db.py   # Firestore: watchlist persistence + Recommendations usage caps
  logic/              # Feature business logic
    pricechecker.py   # Inventory fetch + marketplace scraping + rendering
    matcher.py        # Collection/wantlist fetch and comparison
    lookup.py         # Collection, wantlist, lists fetch + list scraping
    recommend.py      # Taste profile -> Gemini candidates -> Discogs release resolution
    insights.py       # Aggregates collection stats; renders the Insights Dashboard
    charts.py         # SVG chart generators
  utils/              # auth.py (Keychain), common.py (headers), lookup_cache.py, records.py
  models/             # models.py — shared data structures

static/
  css/                # vars, sidebar, components, results, cards, mosaic, insights, lookup,
                      #   reprice, records, tools, main — design tokens + per-feature styles
  js/                 # main, pricechecker, reprice, lookup*, matcher, mosaic, insights,
                      #   grid, records, app-client, utils — global + per-feature UI

templates/
  base.html           # Master layout with sidebar and content slot
  macros.html         # Shared Jinja macros (card grid, etc.)
  landing.html        # Landing page (extends base)
  pricechecker.html   # Price Checker page
  matcher.html        # Matcher page
  lookup.html         # Lookup page
  recommend.html      # Recommendations page
  records.html        # Records page

server/               # Standalone background monitor (not wired to web routes)
  server.py           # Manages Worker threads
  worker.py           # Polls seller inventory; sends Discord webhook on changes
```

---

## API Calls

All requests go through a `cloudscraper` instance to handle Cloudflare. The `User-Agent` header is set in `services/utils/common.py`. Authenticated requests pass an OAuth1 object.

### REST API — `https://api.discogs.com`

| Endpoint | Used in | Route |
|---|---|---|
| `GET /users/{username}/inventory?status=For+Sale` | `pricechecker.py` | `/pricechecker` |
| `GET /users/{username}/collection/folders/0/releases` | `matcher.py`, `lookup.py`, `recommend.py` | `/matcher`, `/lookup`, `/recommend` |
| `GET /users/{username}/wants` | `matcher.py`, `lookup.py` | `/matcher`, `/lookup` |
| `GET /users/{username}/lists` | `lookup.py` | `/lookup` |
| `GET /database/search` | `recommend.py` | `/recommend` |
| `GET /listings/{listing_id}` | `pricechecker_routes.py` | `/reprice` (POST) |
| `POST /listings/{listing_id}` | `pricechecker_routes.py` | `/reprice` (POST) |

Collection, wantlist, and list-index calls are paginated and fetched concurrently with `ThreadPoolExecutor` (5 workers). Price Checker scrapes 10 releases concurrently. Recommendations resolve Gemini suggestions to Discogs releases via `/database/search`, also concurrently.

### AI — Vertex AI (Gemini)

The Recommendations tool calls Gemini through Google's Vertex AI using the `google-genai` SDK (model `gemini-2.5-flash` by default), authenticated with the same service-account credentials as the Google Sheets client. It returns structured JSON suggestions which are then resolved against the Discogs search API. Usage is bounded by a per-IP daily limit and a global monthly round cap.

#### Tuning & cost

A "round" is one Gemini call. A "search" streams up to `_MAX_ROUNDS` rounds, stopping early once `_TARGET_RESULTS` releases resolve (or when Gemini runs out of new candidates). In practice most searches use all 3 rounds, since ~half of each round's candidates are dropped by the owned-collection filter or fail to resolve to a qualifying Discogs vinyl release.

| Knob | Constant | Env override | Default | Where |
|---|---|---|---|---|
| Model | `_MODEL` | `VERTEX_GEMINI_MODEL` | `gemini-2.5-flash` | `recommend.py` |
| Vertex region | `_LOCATION` | `VERTEX_LOCATION` | `us-central1` | `recommend.py` |
| Candidates asked per streaming round | `_CANDIDATES_PER_ROUND` | — | `5` | `recommend.py` |
| Candidates asked per manual "get more" round | `_REFRESH_CANDIDATES` | — | `10` | `recommend_routes.py` |
| Thinking budget (tokens; 0 disables) | `_THINKING_BUDGET` | `VERTEX_THINKING_BUDGET` | `128` | `recommend.py` |
| Target resolved releases per search | `_TARGET_RESULTS` | — | `10` | `recommend_routes.py` |
| Max rounds per search | `_MAX_ROUNDS` | — | `3` | `recommend_routes.py` |
| Per-IP daily round cap | `_IP_DAILY_ROUND_LIMIT` | `RECOMMEND_IP_DAILY_ROUND_LIMIT` | `50` | `recommend_routes.py` |
| Global monthly round cap | `_MONTHLY_ROUND_CAP` | `RECOMMEND_MONTHLY_ROUND_CAP` | `1000` | `recommend.py` |

**Cost (measured):** $0.73 for 121 rounds ≈ **$0.0060/round** (~0.60¢). Each round bills roughly **~2,000 input tokens + ~2,000 output-billed tokens** (the 128-token thinking budget is included in output), against `gemini-2.5-flash` list pricing of ~$0.30/1M input and ~$2.50/1M output — so output dominates (~90%) and scales with candidate count, not round count. Derived caps at this rate:

- **Per search** (~3 rounds) ≈ **$0.018**
- **Per-IP daily cap** (50 rounds) ≈ **$0.30/day/IP**
- **Global monthly cap** (1,000 rounds) ≈ **$6.00/month** — the effective spend ceiling for the feature

Round usage is tracked in Firestore: global monthly count at `usage/gemini_rounds_<YYYY-MM>`, per-IP daily count at `ratelimit/<ip>_<YYYY-MM-DD>`. To translate a target monthly budget into a cap, set `RECOMMEND_MONTHLY_ROUND_CAP ≈ target_dollars ÷ 0.0060` (e.g. a $3/month budget ≈ ~500 rounds). Re-derive the $/round figure if the model, thinking budget, or `_TARGET_RESULTS` changes.

### HTML Scraping — `https://www.discogs.com`

| URL | Used in | Route |
|---|---|---|
| `/sell/release/{release_id}` | `pricechecker.py` | `/pricechecker` |
| `/lists/{list_id}` | `lookup.py` | `/lookup` |

`/sell/release/{release_id}` — parsed with BeautifulSoup; pulls the `mpitems` table for competitor pricing and the `ul.last` element for last-sold date.

`/lists/{list_id}` — parsed with BeautifulSoup; pulls the embedded Apollo cache JSON from `<script id="dsdata">` for release info, thumbnails, per-item comments, and marketplace availability.

### Rate Limits

Every API request the app makes is authenticated, so all requests get Discogs' authenticated limit of **60 requests/minute** (vs. 25/minute for unauthenticated requests). Signed-in users authenticate via OAuth; signed-out users authenticate at the **application level** using the consumer key/secret (`Authorization: Discogs key=…, secret=…`), which carries no user identity but still earns the 60/min tier. Discogs uses a sliding 60-second window — no fixed lockout; slots free up as the window rolls — and throttles per source IP. The `X-Discogs-Ratelimit-Remaining` response header can be read to throttle proactively. See the [Discogs API rate-limiting docs](https://www.discogs.com/developers/accessing.html#page:home,header:home-rate-limiting).

---

## Authentication

Discogs login uses OAuth 1.0a. Click "Login with Discogs" in the sidebar to authorize. Once logged in, the reprice feature becomes available in Price Checker.

On the macOS desktop app, credentials are persisted to the system Keychain so you stay logged in across restarts.

---

## Running Locally

```bash
pip install -r requirements.txt
python main.py
# http://127.0.0.1:8080
```

Deploy:
```bash
gcloud app deploy
```

---

## macOS Desktop App

Package as a standalone macOS .app using `py2app`. The app bundles Flask + static assets and displays the interface in a native `pywebview` window.

```bash
python3 setup.py py2app
# Output: dist/macos/Discogs Toolkit.app
```

Price Checker is enabled in the desktop app (scraping runs locally, not on GAE).

---

## Server Module (`server/`) — Currently Down

Standalone background monitor unrelated to the web routes. A `Worker` polls a seller's inventory on a configurable interval, compares it against the previous snapshot, and sends a Discord webhook notification when listings are added, removed, or repriced. Not currently running.
