import os

_token = os.environ.get("DISCOGS_TOKEN", "")
API_HEADERS = {
    "User-Agent": "DiscogsToolkitApp/1.0",
    **({"Authorization": "Discogs token=" + _token} if _token else {})
}
