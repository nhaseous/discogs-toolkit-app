# discogs-toolkit-app

Flask web app for Discogs marketplace research and collection browsing. Deployed on Google App Engine.

**Live:** https://discogs-toolkit.uc.r.appspot.com

---

## Tools

### Price Checker (`/pricechecker`)
Enter a seller's username. Fetches their entire for-sale inventory, then for each release scrapes the Discogs marketplace to show where the seller's listing ranks among all other listings for that release. Each card shows the full list of competing prices with conditions, the seller's rank, total number of marketplace listings, and last sold date. Cards can be filtered by supply (Lowest / Low / High / Highest) and recency (Recent / Old). Logged-in users can reprice selected listings directly from the UI.

> Price Checker is disabled on Google App Engine (Cloudflare blocks scraping from server IPs). It's available locally and in the macOS desktop app.

### Matcher (`/matcher`)
Enter two usernames — one collection, one wantlist. Returns all releases in the collection that also appear on the wantlist. Two match modes: fuzzy (artist + title + format only) and exact (also includes format description and pressing text). Useful for figuring out what you have that someone else wants, or vice versa.

### User Lookup (`/lookup`)
Enter any Discogs username. Browse their full collection, wantlist, and any public curated lists as a card grid with album art. For a curated list, each card also shows the number of marketplace copies for sale and the lowest price, plus any per-item comments the list owner left.

### Records (`/records`)
Personal collection dashboard backed by Google Sheets. Shows collection stats, inventory, and sold records. Restricted to a single user.

---

## Project Structure

```
main.py               # Flask app — all routes, context processor, session config
assets.py             # SVG and HTML snippet constants loaded at startup
mac_main.py           # macOS .app entry point
setup.py              # py2app build config for macOS .app

helper/
  pricechecker.py     # Price Checker — inventory fetch + marketplace scraping + rendering
  matcher.py          # Matcher — collection/wantlist fetch and comparison
  lookup.py           # Lookup — collection, wantlist, lists fetch + list scraping
  records.py          # Records — Google Sheets load + dashboard rendering
  auth.py             # macOS Keychain credential persistence
  common.py           # Shared API headers

static/
  css/
    vars.css          # Design tokens, reset, global layout
    sidebar.css       # Left nav sidebar
    components.css    # Search bar, spinner, badges
    results.css       # Result cards, tabs, pagination, mosaics
    tools.css         # Landing page tool cards
  js/
    main.js           # Global UI: sidebar, tabs, pagination, badge filters, tooltips
    pricechecker.js   # Price Checker: filter pills, card refresh, reprice flow
    records.js        # Records: tab switching

templates/
  base.html           # Master layout with sidebar and content slot
  landing.html        # Landing page (extends base)
  pricechecker.html   # Price Checker page
  matcher.html        # Matcher page
  lookup.html         # Lookup page
  records.html        # Records page

server/               # Standalone background monitor (not wired to web routes)
  server.py           # Manages Worker threads
  worker.py           # Polls seller inventory; sends Discord webhook on changes
```

---

## API Calls

All requests go through a `cloudscraper` instance to handle Cloudflare. The `User-Agent` header is set in `helper/common.py`. Authenticated requests pass an OAuth1 object.

### REST API — `https://api.discogs.com`

| Endpoint | Used in | Route |
|---|---|---|
| `GET /users/{username}/inventory?status=For+Sale` | `pricechecker.py` | `/pricechecker` |
| `GET /users/{username}/collection/folders/0/releases` | `matcher.py`, `lookup.py` | `/matcher`, `/lookup` |
| `GET /users/{username}/wants` | `matcher.py`, `lookup.py` | `/matcher`, `/lookup` |
| `GET /users/{username}/lists` | `lookup.py` | `/lookup` |
| `GET /listings/{listing_id}` | `main.py` | `/reprice` (POST) |
| `POST /listings/{listing_id}` | `main.py` | `/reprice` (POST) |

Collection, wantlist, and list-index calls are paginated and fetched concurrently with `ThreadPoolExecutor` (5 workers). Price Checker scrapes 10 releases concurrently.

### HTML Scraping — `https://www.discogs.com`

| URL | Used in | Route |
|---|---|---|
| `/sell/release/{release_id}` | `pricechecker.py` | `/pricechecker` |
| `/lists/{list_id}` | `lookup.py` | `/lookup` |

`/sell/release/{release_id}` — parsed with BeautifulSoup; pulls the `mpitems` table for competitor pricing and the `ul.last` element for last-sold date.

`/lists/{list_id}` — parsed with BeautifulSoup; pulls the embedded Apollo cache JSON from `<script id="dsdata">` for release info, thumbnails, per-item comments, and marketplace availability.

### Rate Limits

Unauthenticated: 25 requests/minute. With OAuth: 240 requests/minute. Discogs uses a sliding 60-second window — no fixed lockout; slots free up as the window rolls. The `X-Discogs-Ratelimit-Remaining` response header can be read to throttle proactively.

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
