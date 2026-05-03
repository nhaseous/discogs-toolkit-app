# discogs-toolkit-app

Flask web app for Discogs marketplace research and collection browsing. Deployed on Google App Engine.

**Live:** https://discogs-toolkit.uc.r.appspot.com

---

## Tools

### Price Checker (`/pricechecker`)
Enter a seller's username. Fetches their entire for-sale inventory, then for each release scrapes the Discogs marketplace to show where the seller's listing ranks among all other listings for that release. Each card shows the full list of competing prices with conditions, the seller's rank position, total number of marketplace listings, and last sold date. Cards can be filtered by supply (Lowest / Low / High / Highest) and recency (Recent sale within 10 days / Old sale over a year ago). Useful for making pricing decisions and spotting underpriced or rare items.

### Matcher (`/matcher`)
Enter two usernames — one collection, one wantlist. Returns all releases in the collection that also appear on the wantlist. Two match modes: fuzzy (artist + title + format only) and exact (also includes format description and pressing text). Useful for figuring out what you have that someone else wants, or vice versa.

### User Lookup (`/lookup`)
Enter any Discogs username. Browse their full collection, wantlist, and any public curated lists as a card grid with album art. For a curated list, each card also shows the number of marketplace copies for sale and the lowest price (clicking it goes to the sell page), plus any per-item comments the list owner left.

---

## Project Structure

```
main.py                  # Flask app — all routes, page layout, inline JS
helper/
  pricechecker.py        # Price Checker — inventory fetch + marketplace scraping
  matcher.py             # Matcher — collection/wantlist fetch and comparison
  lookup.py              # Lookup — collection, wantlist, lists fetch + list page scraping
  common.py              # Shared API headers (User-Agent, optional auth token)
static/
  style.css              # All styles
server/
  worker.py              # Background inventory monitor (see below)
  server.py              # Server that manages workers
```

---

## API Calls

All requests go through a `cloudscraper` instance to handle Cloudflare. Auth headers and User-Agent are set in `helper/common.py` and passed to every REST call.

### REST API — `https://api.discogs.com`

| Endpoint | Used in | Route |
|---|---|---|
| `GET /users/{username}/inventory?status=For+Sale` | `pricechecker.py` → `get_inventory_ids` | `/pricechecker` |
| `GET /users/{username}/collection/folders/0/releases` | `matcher.py` → `get_collection` | `/matcher` |
| `GET /users/{username}/collection/folders/0/releases` | `lookup.py` → `get_collection` | `/lookup` |
| `GET /users/{username}/wants` | `matcher.py` → `get_wantlist` | `/matcher` |
| `GET /users/{username}/wants` | `lookup.py` → `get_wantlist` | `/lookup` |
| `GET /users/{username}/lists` | `lookup.py` → `get_lists` | `/lookup` |

All collection, wantlist, and list-index calls are paginated and fetched concurrently with `ThreadPoolExecutor` (5 workers).

### HTML Scraping — `https://www.discogs.com`

| URL | Used in | Route |
|---|---|---|
| `/sell/release/{release_id}` | `pricechecker.py` → `get_listings` | `/pricechecker` |
| `/lists/{list_id}` | `lookup.py` → `get_list_releases` | `/lookup` |

`/sell/release/{release_id}` — parsed with BeautifulSoup; pulls the `mpitems` table for competitor pricing, seller rank, and the last-sold date from the `ul.last` element. One scrape per release, fired concurrently (10 workers).

`/lists/{list_id}` — parsed with BeautifulSoup; pulls the embedded Apollo cache JSON from `<script id="dsdata">` for release titles, artists, thumbnails, per-item comments, and marketplace availability (`copiesForSale`, `lowestPrice`). Paginated and fetched concurrently (5 workers).

### Rate Limits

Unauthenticated: 25 requests/minute. With a personal access token: 240 requests/minute. Set `DISCOGS_TOKEN` in the environment to enable — `helper/common.py` picks it up and adds the `Authorization` header automatically.

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

You can package the application as a standalone macOS desktop app using `py2app`. This creates a `.app` bundle that runs a local Flask server and displays the interface in a native `webview` window.

### Prerequisites
- macOS
- Python 3.9+
- Dependencies installed via `requirements.txt`

### Build Instructions
Run the following command to generate the build:
```bash
python3 setup.py py2app
```

### Build Artifacts
- **`build/`**: Temporary directory used during the build process (ignored by git).
- **`dist/macos/Discogs Toolkit.app`**: The final standalone application.

The build script automatically moves the completed bundle to `dist/macos/` and cleans up the intermediate `dist/` artifacts. The application includes your `.env` file and all static assets.

---

## Server Module (`server/`) — Currently Down

Standalone background monitor unrelated to the web routes. A `Worker` polls a seller's inventory on a configurable interval, compares it against the previous snapshot, and sends a Discord webhook notification when listings are added, removed, or repriced. Managed by `server.py`. Not currently running.
