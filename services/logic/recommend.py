"""
Record recommendations via Vertex AI (Gemini).

Stage 1 (taste profile) reuses the same collection aggregation the Insights
dashboard runs (services/logic/insights.py), so a recommendation request adds no
new Discogs-side computation — it just reshapes the existing genre/style/artist/
label rankings into a compact text profile.

Stage 2 (the Gemini call) authenticates with the *same* service account JSON the
Google Sheets client already uses (GOOGLE_SA_KEY_B64), so no separate API key is
needed and the feature works on GAE and in the macOS desktop build alike.

Stage 3 (resolving each suggestion to a real Discogs release) is intentionally
NOT implemented yet — this module returns Gemini's raw text so the Vertex setup
can be verified before the Discogs-resolution layer is built.
"""
import base64
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.clients import firestore_db
from services.clients.discogs_client import request_with_retry
from services.logic import insights as insights_helper
from services.utils.common import API_HEADERS as _API_HEADERS


class VertexConfigError(RuntimeError):
    """Raised when Vertex AI credentials / project can't be resolved.

    Surfaced to the user so a misconfigured setup is obvious during the
    verification step rather than failing as an opaque 500.
    """


# Defaults are overridable via env so the model/region can be tuned without a
# code change. Confirm the exact Gemini model ID against the Vertex model garden
# for your project — available IDs evolve over time.
_MODEL = os.environ.get("VERTEX_GEMINI_MODEL", "gemini-2.5-flash")
_LOCATION = os.environ.get("VERTEX_LOCATION", "us-central1")
_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

_SEARCH_URL = "https://api.discogs.com/database/search"
# Default per-round Gemini ask for the initial streaming rounds. Manual "get more"
# refreshes over-ask instead (see _REFRESH_CANDIDATES in recommend_routes.py),
# because ~half of each round's candidates are lost to the owned-collection filter
# and to candidates with no qualifying Discogs vinyl release — so a lone refresh
# round on a large collection would otherwise sometimes net zero.
_CANDIDATES_PER_ROUND = 5

# Fixed Gemini thinking budget (tokens). Default 2.5-flash dynamic thinking adds
# ~12s/round; a small cap keeps taste reasoning while making rounds ~3-4x faster.
# Override via env. 0 disables thinking entirely.
_THINKING_BUDGET = int(os.environ.get("VERTEX_THINKING_BUDGET", "128"))

# Global monthly cost guard: each round is one Gemini call. A round is ~0.1–0.2¢,
# so 1000 rounds/month ≈ $1–$2 — comfortably under the $5 budget. Override via env.
# The Cloud Billing budget is the alerting backstop.
_MONTHLY_ROUND_CAP = int(os.environ.get("RECOMMEND_MONTHLY_ROUND_CAP", "1000"))


class CapReachedError(RuntimeError):
    """Raised when the global monthly Gemini-round cap is hit before any
    recommendations were produced, so the route can show a 'paused' message."""

SYSTEM_PROMPT = (
    "You are a vinyl and music recommendation expert with deep knowledge of "
    "Discogs, record labels, and music history. Given a collector's taste "
    "profile (their most-collected genres, styles, artists, and labels), "
    "recommend specific records they most likely do NOT already own but would "
    "love. Favour depth and discovery over obvious mainstream picks. Keep each "
    "reason to a single sentence grounded in the profile."
)

# Bio is requested only on the first Gemini round of a recommendation (the only
# one whose result is kept), so top-up rounds don't pay to generate it. The
# instruction is appended to the per-round prompt when `want_bio` is set.
_BIO_INSTRUCTION = (
    "Also write a warm, insightful bio of exactly 2 sentences that summarises "
    "this collector's taste — the genres, eras, and sensibilities their "
    "collection reveals — addressed to the collector in the second person. "
)

# Lazily-built singleton genai client. Constructed on first use so importing this
# module (e.g. at app startup) never requires Vertex to be reachable.
_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    # Import here so a missing google-genai install surfaces a clear config
    # error at request time rather than breaking app import.
    try:
        from google import genai
    except ImportError as e:
        raise VertexConfigError(
            "google-genai is not installed (add `google-genai` to requirements.txt)."
        ) from e

    from google.oauth2 import service_account

    # Mirror services/clients/google_client.py credential resolution: explicit
    # key file (local dev) → base64 env var (GAE/desktop) → application default.
    project = None
    key_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if key_file and os.path.exists(key_file):
        creds = service_account.Credentials.from_service_account_file(key_file, scopes=_SCOPES)
        project = creds.project_id
    elif os.environ.get("GOOGLE_SA_KEY_B64"):
        info = json.loads(base64.b64decode(os.environ["GOOGLE_SA_KEY_B64"]))
        creds = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
        project = info.get("project_id")
    else:
        import google.auth
        creds, project = google.auth.default(scopes=_SCOPES)

    project = os.environ.get("GCP_PROJECT") or project
    if not project:
        raise VertexConfigError("No GCP project could be resolved for Vertex AI.")

    try:
        _client = genai.Client(
            vertexai=True, project=project, location=_LOCATION, credentials=creds
        )
    except Exception as e:
        raise VertexConfigError("Failed to initialise the Vertex AI client: {0}".format(e)) from e
    return _client


def build_taste_profile(items, max_each=15):
    """Turn collection items (lookup `_release_dict` shape) into a compact text
    profile for the prompt, reusing the Insights aggregation."""
    data = insights_helper.get_collection_insights(items)

    def fmt(pairs):
        return ", ".join("{0} ({1})".format(name, count) for name, count in pairs[:max_each]) or "—"

    lines = [
        "Collection size: {0} releases".format(len(items)),
        "Top genres: {0}".format(fmt(data["all_genres"])),
        "Top styles: {0}".format(fmt(data["all_subgenres"])),
        "Top artists: {0}".format(fmt(data["all_artists"])),
        "Top labels: {0}".format(fmt(data["all_labels"])),
    ]
    decades = [(d["name"], d["value"]) for d in data.get("decade_pie", [])]
    if decades:
        lines.append("Decades: " + ", ".join("{0} ({1})".format(n, v) for n, v in decades[:max_each]))
    return "\n".join(lines)


def _recommendation_item_schema():
    """Schema for one {artist, album, reason} recommendation object."""
    from google.genai import types
    return types.Schema(
        type=types.Type.OBJECT,
        required=["artist", "album", "reason"],
        properties={
            "artist": types.Schema(type=types.Type.STRING),
            "album": types.Schema(type=types.Type.STRING),
            "reason": types.Schema(type=types.Type.STRING),
        },
    )


def _recommendation_schema(want_bio):
    """Structured-output schema for the Gemini response. With `want_bio` the
    response is an object of {bio, recommendations}; without it (top-up rounds,
    where the bio would be discarded) it's a bare array of recommendations — a
    smaller payload the model generates faster."""
    from google.genai import types
    items = types.Schema(type=types.Type.ARRAY, items=_recommendation_item_schema())
    if not want_bio:
        return items
    return types.Schema(
        type=types.Type.OBJECT,
        required=["bio", "recommendations"],
        properties={"bio": types.Schema(type=types.Type.STRING), "recommendations": items},
    )


def fetch_recommendations(profile_text, n, exclude_titles=None, new_artists=False,
                          want_bio=True):
    """Ask Gemini for `n` recommendations and return a `(bio, recommendations)`
    tuple. `recommendations` is a list of {artist, album, reason} dicts; `bio`
    is a 2-sentence taste-profile summary, or "" when `want_bio` is False.

    Uses Vertex structured output (response_schema) so the model returns
    validated JSON instead of a delimited text format we have to hand-parse.

    The bio is requested only on the first round of a recommendation (the only
    one whose bio is kept), so top-up rounds skip generating it — both the prompt
    instruction and the schema's `bio` field are dropped when `want_bio` is False.

    `exclude_titles` (a list of "Artist - Album" strings already considered) is
    fed back into the prompt so top-up rounds don't repeat earlier suggestions.

    When `new_artists` is set, the prompt also instructs the model to only
    suggest artists not already in the collection — a yield mitigation paired
    with the hard owned-artist filter in `get_recommendation_cards`.

    Raises VertexConfigError if the client can't be built; other exceptions
    propagate to the caller (the route surfaces them for debugging).
    """
    from google.genai import types
    client = _get_client()
    avoid = ""
    if exclude_titles:
        avoid = (" Do NOT suggest any of these already-considered records: "
                 + "; ".join(exclude_titles) + ".")
    new_artist_rule = ""
    if new_artists:
        new_artist_rule = (
            " Every recommendation must be by an artist the collector does NOT "
            "already own — do not recommend any artist listed in their top "
            "artists above, or any other artist already in their collection. "
            "Recommend only artists that are new to this collector."
        )
    bio_rule = _BIO_INSTRUCTION if want_bio else ""
    prompt = (
        "Here is the collector's taste profile:\n\n{profile}\n\n"
        "Recommend exactly {n} records they likely don't own but would love. "
        "Only suggest records the collector does NOT already own — favour fresh "
        "discoveries over their existing collection.{avoid}{newartist} {bio}For "
        "each, give the primary artist, the album title, and a one-sentence "
        "reason grounded in their taste."
    ).format(profile=profile_text, n=n, avoid=avoid, newartist=new_artist_rule, bio=bio_rule)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=_recommendation_schema(want_bio),
        # Cap the reasoning budget: gemini-2.5-flash defaults to *dynamic*
        # thinking, which burns ~12s/round reasoning before emitting any JSON —
        # the dominant cost of a round. A small fixed budget keeps enough
        # reasoning for taste-profile fit while cutting a round from ~14s to ~4s.
        thinking_config=types.ThinkingConfig(thinking_budget=_THINKING_BUDGET),
    )
    resp = client.models.generate_content(model=_MODEL, contents=prompt, config=config)

    # Prefer the SDK's parsed value; fall back to decoding the raw text.
    data = getattr(resp, "parsed", None)
    if data is None:
        text = getattr(resp, "text", None)
        if not text:
            return "", []
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            return "", []

    # want_bio → object {bio, recommendations}; otherwise → bare array.
    if want_bio:
        if not isinstance(data, dict):
            return "", []
        bio = (data.get("bio") or "").strip()
        recs = data.get("recommendations")
        recs = recs if isinstance(recs, list) else []
    else:
        bio = ""
        recs = data if isinstance(data, list) else []
    return bio, [d for d in recs if isinstance(d, dict)]


def _norm(s):
    s = (s or "").lower().strip()
    s = re.sub(r"^the\s+", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def _key(artist, album):
    return _norm(artist) + "|" + _norm(album)


def owned_keys(items):
    """Normalized {artist|album} keys for every release in the collection, used
    to filter out recommendations the collector already owns."""
    keys = set()
    for item in items:
        title = item.get("title", "")
        artists = item.get("artist") or []
        if isinstance(artists, str):
            artists = [artists]
        for a in artists:
            keys.add(_key(a, title))
    return keys


def owned_artists(items):
    """Normalized artist names for every release in the collection, used by the
    'new artists only' filter to drop recommendations by artists already owned
    (even when the specific album is new)."""
    names = set()
    for item in items:
        artists = item.get("artist") or []
        if isinstance(artists, str):
            artists = [artists]
        for a in artists:
            key = _norm(a)
            if key:
                names.add(key)
    return names


def collect_candidates(profile_text, n, exclude_keys, exclude_titles, new_artists=False,
                       want_bio=True):
    """Run one Gemini round and return a `(bio, candidates)` tuple, dropping any
    candidate whose artist|album key is in `exclude_keys` (owned or
    already-suggested). `bio` is "" unless `want_bio` is set."""
    bio, recs = fetch_recommendations(profile_text, n, exclude_titles=exclude_titles,
                                      new_artists=new_artists, want_bio=want_bio)
    out, seen = [], set()
    for rec in recs:
        artist = (rec.get("artist") or "").strip()
        album = (rec.get("album") or "").strip()
        reason = (rec.get("reason") or "").strip()
        if not artist or not album:
            continue
        key = _key(artist, album)
        if key in exclude_keys or key in seen:
            continue
        seen.add(key)
        out.append({"artist": artist, "album": album, "reason": reason})
    return bio, out


# ---- Step 3: resolve candidates to real Discogs vinyl releases -------------

def owned_release_ids(items):
    """Discogs release IDs already in the collection, parsed from each item's
    release URL — a stronger owned-check than artist/title text matching."""
    ids = set()
    for item in items:
        m = re.search(r"/release/(\d+)", item.get("url", "") or "")
        if m:
            ids.add(m.group(1))
    return ids


def _tokens(s):
    """Lowercased alphanumeric word tokens, with a leading 'the' dropped to match
    `_norm`'s article handling."""
    s = re.sub(r"^the\s+", "", (s or "").lower().strip())
    return {t for t in re.split(r"[^a-z0-9]+", s) if t}


def _coverage(needle, haystack_tokens):
    """Fraction of `needle`'s tokens present in `haystack_tokens` (0.0–1.0)."""
    nt = _tokens(needle)
    if not nt:
        return 0.0
    return len(nt & haystack_tokens) / len(nt)


def _result_matches(artist, album, result, artist_min=0.5, album_min=0.6):
    """Guard against the search returning an unrelated release. Discogs formats
    result titles as "Artist - Album", so we fuzzy-match the candidate against
    the whole title by token coverage rather than exact substring: this tolerates
    word reordering, extra qualifiers ("Quintet", "(Remastered)"), and featured
    artists that broke the old strict `in` check. We require most of the album's
    tokens and at least half the artist's tokens to appear."""
    if not _tokens(album):
        return False
    title_tokens = _tokens(result.get("title", ""))
    return (_coverage(album, title_tokens) >= album_min
            and _coverage(artist, title_tokens) >= artist_min)


def _run_search(params, scraper, auth):
    """Execute one Discogs search; return its results list ([] on any failure)."""
    try:
        resp = request_with_retry(scraper, "GET", _SEARCH_URL, params=params,
                                  headers=_API_HEADERS, auth=auth, max_429_retries=0)
    except Exception:
        return []
    if resp is None or resp.status_code != 200:
        return []
    try:
        return resp.json().get("results", []) or []
    except Exception:
        return []


def _pick_match(artist, album, results):
    """First result that is Vinyl, not Unofficial, and fuzzy-matches the
    candidate. Returns the result dict or None."""
    for r in results:
        formats = [str(f).lower() for f in (r.get("format") or [])]
        if "vinyl" not in formats:                      # need Vinyl present
            continue
        if any("unofficial" in f for f in formats):     # exclude Unofficial Release
            continue
        if not _result_matches(artist, album, r):       # exclude unrelated matches
            continue
        return r
    return None


def search_vinyl_release(artist, album, scraper, auth=None, budget=None):
    """Find a Discogs release for `artist`/`album` available on Vinyl and not an
    Unofficial Release. Returns the matching search-result dict, or None.

    Tries progressively looser searches so a candidate isn't lost to one rigid
    query: (1) strict structured search on the Vinyl format, (2) a free-text
    query post-filtered for vinyl. Stops at the first qualifying match."""
    strategies = [
        {"artist": artist, "release_title": album, "format": "Vinyl",
         "type": "release", "per_page": 15},
        {"q": "{0} {1}".format(artist, album), "format": "Vinyl",
         "type": "release", "per_page": 25},
    ]
    for params in strategies:
        if budget is not None and not budget.take():
            return None
        match = _pick_match(artist, album, _run_search(params, scraper, auth))
        if match:
            return match
    return None


def _card_from(candidate, result):
    """Build a lookup_grid-shaped card from a candidate + its resolved release.
    The Gemini reason becomes `comment`, rendered like a list-item comment."""
    rid = str(result.get("id", ""))
    fmts = [f for f in (result.get("format") or []) if f]
    return {
        "artist": candidate["artist"],
        "title": candidate["album"],
        "url": "https://www.discogs.com/release/{0}".format(rid) if rid else "",
        "cover_image": result.get("cover_image", ""),
        "thumb": result.get("thumb", ""),
        "format": ", ".join(fmts),
        "comment": candidate.get("reason", ""),
    }


def run_recommendation_round(items, scraper, auth=None, budget=None,
                             considered=None, seen_ids=None, new_artists=False,
                             want_bio=True, n_candidates=None):
    """Run ONE Gemini round and resolve its candidates to Vinyl cards.

    This is the per-round core the streaming `/recommend/batch` endpoint calls
    once per HTTP request, and which `get_recommendation_cards` loops over for
    the all-at-once path. It is stateless across calls: the caller round-trips
    `considered` (a list of {"artist","album"} dicts already suggested in prior
    rounds — fed back to Gemini to avoid repeats and to dedupe) and `seen_ids`
    (release IDs already rendered, to dedupe resolved releases across rounds).

    `want_bio` should be True only for the first round of a recommendation; later
    rounds skip generating the (discarded) bio to keep their Gemini call cheaper.

    `n_candidates` overrides how many candidates this round asks Gemini for
    (defaults to `_CANDIDATES_PER_ROUND`); manual "get more" refreshes pass a
    higher count to offset per-round attrition.

    Returns a dict:
      cards      — newly resolved cards this round (lookup_grid-shaped)
      bio        — Gemini's 2-sentence taste summary ("" when `want_bio` is False)
      considered — updated {"artist","album"} list to pass to the next round
      seen_ids   — updated sorted list of release IDs to pass to the next round
      capped     — True if the global monthly cap blocked this round (no call made)
      exhausted  — True if Gemini returned no usable new candidates

    When `new_artists` is set, candidates by an already-owned artist are dropped
    before any Discogs search, and Gemini is told to avoid owned artists.
    """
    considered = [dict(c) for c in (considered or [])]
    seen_ids = set(str(i) for i in (seen_ids or []))

    # Global cost guard: count this round against the monthly cap before
    # spending a Gemini call.
    if not firestore_db.consume_gemini_round(_MONTHLY_ROUND_CAP):
        return {"cards": [], "bio": "", "considered": considered,
                "seen_ids": sorted(seen_ids), "capped": True, "exhausted": False}

    owned_text = owned_keys(items)
    owned_ids = owned_release_ids(items)
    owned_art = owned_artists(items) if new_artists else set()

    suggested_keys = {_key(c["artist"], c["album"]) for c in considered}
    suggested_titles = ["{0} - {1}".format(c["artist"], c["album"]) for c in considered]

    bio, candidates = collect_candidates(
        build_taste_profile(items), n_candidates or _CANDIDATES_PER_ROUND,
        exclude_keys=owned_text | suggested_keys,
        exclude_titles=suggested_titles,
        new_artists=new_artists,
        want_bio=want_bio,
    )

    # Record every raw candidate as "considered" so future rounds don't
    # re-suggest it, even ones we're about to drop for being an owned artist.
    for c in candidates:
        considered.append({"artist": c["artist"], "album": c["album"]})

    # 'New artists only': drop candidates by an artist already owned before
    # spending any Discogs searches on them.
    if new_artists:
        candidates = [c for c in candidates if _norm(c["artist"]) not in owned_art]

    cards = []
    if candidates:
        # Resolve candidates concurrently (network-bound), then assemble in order
        # so dedupe stays single-threaded.
        resolved = [None] * len(candidates)
        with ThreadPoolExecutor(max_workers=5) as ex:
            futs = {
                ex.submit(search_vinyl_release, c["artist"], c["album"], scraper, auth, budget): i
                for i, c in enumerate(candidates)
            }
            for fut in as_completed(futs):
                i = futs[fut]
                try:
                    resolved[i] = fut.result()
                except Exception:
                    resolved[i] = None

        for c, r in zip(candidates, resolved):
            if not r:
                continue
            rid = str(r.get("id", ""))
            if not rid or rid in owned_ids or rid in seen_ids:
                continue
            seen_ids.add(rid)
            cards.append(_card_from(c, r))

    return {"cards": cards, "bio": bio, "considered": considered,
            "seen_ids": sorted(seen_ids), "capped": False,
            "exhausted": not candidates}


def get_recommendation_cards(items, scraper, auth=None, budget=None, min_results=10,
                             max_rounds=3, new_artists=False):
    """All-at-once pipeline: loop `run_recommendation_round` until at least
    `min_results` cards are found or `max_rounds` Gemini rounds are spent,
    aggregating across rounds. Returns a `(cards, bio)` tuple.

    Raises CapReachedError if the monthly cap blocks the very first round (so the
    route can show a 'paused' notice); a cap hit after some cards exist just
    stops and returns what was found. The streaming `/recommend/batch` endpoint
    drives the same rounds itself, so this remains the non-streaming entry point."""
    cards, bio, considered, seen_ids = [], "", [], []
    for _round in range(max_rounds):
        if len(cards) >= min_results:
            break
        res = run_recommendation_round(items, scraper, auth=auth, budget=budget,
                                       considered=considered, seen_ids=seen_ids,
                                       new_artists=new_artists, want_bio=(_round == 0))
        if res["capped"]:
            if not cards:
                raise CapReachedError()
            break
        if not bio and res["bio"]:
            bio = res["bio"]
        considered = res["considered"]
        seen_ids = res["seen_ids"]
        cards.extend(res["cards"])
        if res["exhausted"]:
            break
    return cards, bio
