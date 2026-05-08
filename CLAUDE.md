# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Discogs Toolkit is a Flask web app for Discogs marketplace research and collection browsing. It has four tools:
- **Price Checker** (`/pricechecker`): scrapes a seller's inventory and shows where each listing ranks among all marketplace listings for the same release. Disabled on GAE (Cloudflare blocks scraping from server IPs); only available locally and in the macOS desktop app.
- **Matcher** (`/matcher`): finds overlap between one user's collection and another user's wantlist
- **Lookup** (`/lookup`): browse any user's collection, wantlist, and curated lists as a card grid
- **Records** (`/records`): personal collection dashboard backed by Google Sheets; restricted to user `curefortheitch`

Deployed on Google App Engine. Live at: https://discogs-toolkit.uc.r.appspot.com

Also ships as a standalone macOS desktop app (built with `py2app` + `pywebview`).

## Tech Stack

- **Python/Flask** — web framework, all routes in `main.py`
- **cloudscraper** — wraps `requests` to bypass Cloudflare on Discogs HTML pages
- **BeautifulSoup4** — parses scraped HTML marketplace pages
- **Discogs REST API** — used directly for collection, wantlist, inventory, and list data
- **requests-oauthlib** — OAuth 1.0a flow for Discogs login (`/login` → `/callback`)
- **ThreadPoolExecutor** — concurrent scraping; 10 workers in Price Checker, 5 in Matcher/Lookup
- **gspread + google-auth** — Google Sheets access for the Records dashboard
- **Google App Engine** — production deployment (`app.yaml`, `runtime: python312`)
- **pywebview + pyobjc** — native macOS .app wrapper (macOS only)

## Key Files and Directories

```
main.py               # Flask entry point — all routes, context processor, session config
assets.py             # Loads SVGs and HTML snippets into module-level constants at startup
mac_main.py           # macOS .app entry point — starts Flask + opens pywebview window
setup.py              # py2app config for building the macOS .app bundle

helper/
  auth.py             # macOS Keychain credential persistence (save/get/delete)
  common.py           # Shared API headers (User-Agent)
  pricechecker.py     # Price Checker — inventory fetch, marketplace scraping, HTML rendering
  matcher.py          # Matcher — collection/wantlist fetch and comparison
  lookup.py           # Lookup — collection, wantlist, lists fetch + list page scraping
  records.py          # Records — Google Sheets load + HTML table/dashboard rendering

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
    records.js        # Records dashboard: tab switching between panels

templates/
  base.html           # Master layout: sidebar nav, stylesheet links, content slot, main.js
  landing.html        # Empty (extends base)
  pricechecker.html   # Extends base; sets window.TOOLKIT_CONFIG; loads pricechecker.js
  matcher.html        # Extends base
  lookup.html         # Extends base
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
| `/matcher` | GET | Matcher UI | Optional |
| `/lookup` | GET | Lookup UI | Optional |
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

On a successful `/callback`, tokens are written to the Flask session. On macOS, they're also persisted to Keychain via `helper/auth.py` so the user stays logged in across app restarts. A `before_request` hook (`_load_persistent_auth`) restores Keychain credentials into the session on each request if the session is empty.

Price Checker is gated by `_is_price_checker_enabled()`: returns True only on localhost or when running as a frozen macOS app.

## APIs

**Base URL:** `https://api.discogs.com`  
**Docs:** https://www.discogs.com/developers

None of the calls this app makes require authentication — they all access public user data. Discogs enforces rate limits using a sliding 60-second window: unauthenticated requests are capped at 25/minute; adding a personal access token header raises that to 240/minute. The `X-Discogs-Ratelimit-Remaining` response header can be read to throttle proactively before hitting HTTP 429.

### REST API endpoints in use

| Endpoint | Used in | Notes |
|---|---|---|
| `GET /users/{username}/inventory` | `pricechecker.py` | Returns seller's for-sale listings. Paginated. |
| `GET /users/{username}/collection/folders/0/releases` | `lookup.py`, `matcher.py` | Folder `0` is the "All" folder. Returns 401/403 if private. |
| `GET /users/{username}/wants` | `lookup.py`, `matcher.py` | Returns 401/403 if private. |
| `GET /users/{username}/lists` | `lookup.py` | Returns the user's curated lists index. |
| `GET /listings/{listing_id}` | `main.py` `/reprice` | Fetches current listing data before updating. |
| `POST /listings/{listing_id}` | `main.py` `/reprice` | Updates a listing's price (requires OAuth). |

### HTML scraping endpoints in use

These use `cloudscraper` + BeautifulSoup rather than the REST API:

| URL | Used in | Notes |
|---|---|---|
| `https://www.discogs.com/sell/release/{release_id}` | `pricechecker.py` | Marketplace listings page; parses the `mpitems` table for pricing. |
| `https://www.discogs.com/lists/{list_id}` | `lookup.py` | List detail page; parses the embedded `<script id="dsdata">` Apollo cache JSON for items, thumbnails, and per-item comments. Paginated via `?page=N`. |

## Additional Documentation

- [Architectural Patterns](.claude/docs/architectural_patterns.md) — HTML-as-strings rendering, scraping patterns, data flow
