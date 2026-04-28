# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Discogs Toolkit is a Flask web app for Discogs marketplace research. It has two tools:
- **Price Checker**: scrapes a seller's inventory and shows where each listing ranks among all marketplace listings for the same release
- **Matcher**: finds overlap between one user's collection and another user's wantlist

Deployed on Google App Engine. Live at: https://discogs-toolkit.uc.r.appspot.com

## Tech Stack

- **Python/Flask** — web framework, all routes in `main.py`
- **cloudscraper** — wraps `requests` to bypass Cloudflare on Discogs HTML pages
- **BeautifulSoup4** — parses scraped HTML marketplace pages
- **Discogs REST API** — used directly for collection and wantlist data (no scraping needed)
- **ThreadPoolExecutor** — concurrent scraping; 10 workers in Price Checker, 5 in Matcher
- **Google App Engine** — production deployment (`app.yaml`, `runtime: python312`)

## Key Directories

- `main.py` — Flask app entry point; all routes, the shared `page_layout()` function, and all inline JS
- `helper/pricechecker.py` — Price Checker data fetching, scraping, and HTML rendering
- `helper/matcher.py` — Matcher API fetching and data processing
- `server/` — standalone background monitoring system (not wired into the web routes); sends Discord webhook notifications when a seller's inventory changes
- `static/` — CSS (`style.css`) and image assets

## Commands

```bash
# Run dev server (http://127.0.0.1:8080)
python main.py

# Install dependencies
pip install -r requirements.txt

# Deploy to Google App Engine
gcloud app deploy
```

No test suite exists.

## APIs

**Base URL:** `https://api.discogs.com`  
**Docs:** https://www.discogs.com/developers

None of the calls this app makes require authentication — they all access public user data. Discogs enforces rate limits using a sliding 60-second window: unauthenticated requests are capped at 25/minute; adding a personal access token header (`Authorization: Discogs token={token}`) raises that to 240/minute. There is no fixed lockout period — slots free up as the 60-second window rolls. The `X-Discogs-Ratelimit-Remaining` response header can be read to throttle proactively before hitting HTTP 429.

### REST API endpoints in use

| Endpoint | Used in | Notes |
|---|---|---|
| `GET /users/{username}/inventory` | `pricechecker.py` | Returns seller's for-sale listings. Paginated (`per_page`, `page`). |
| `GET /users/{username}/collection/folders/0/releases` | `lookup.py`, `matcher.py` | Folder `0` is the "All" folder. Returns 401/403 if collection is private. |
| `GET /users/{username}/wants` | `lookup.py`, `matcher.py` | Returns 401/403 if wantlist is private. |
| `GET /users/{username}/lists` | `lookup.py` | Returns the user's curated lists index. |

### HTML scraping endpoints in use

These use `cloudscraper` + BeautifulSoup rather than the REST API:

| URL | Used in | Notes |
|---|---|---|
| `https://www.discogs.com/sell/release/{release_id}` | `pricechecker.py` | Marketplace listings page; parses the `mpitems` table for pricing. |
| `https://www.discogs.com/lists/{list_id}` | `lookup.py` | List detail page; parses the embedded `<script id="dsdata">` Apollo cache JSON for items, thumbnails, and per-item comments. Paginated via `?page=N`. |

## Additional Documentation

- [Architectural Patterns](.claude/docs/architectural_patterns.md) — HTML-as-strings rendering, JS embedding, scraping patterns, data flow
