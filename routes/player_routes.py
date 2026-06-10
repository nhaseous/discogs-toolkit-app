from flask import Blueprint, request, jsonify

from services.logic import player as player_helper

player_bp = Blueprint('player', __name__)


@player_bp.route("/player/resolve", methods=["POST"])
def player_resolve():
    """Resolve a Discogs release (artist + album title) to an Apple Music album
    for the Lookup page's in-app preview player.

    Stateless and tokenless: backed entirely by the public iTunes Search API, so
    it adds nothing to authenticate and no Discogs request budget is spent. Always
    returns 200; `found: false` simply means Apple has no confident match and the
    client shows a "not on Apple Music" state for that card.
    """
    data = request.get_json(silent=True) or {}
    artist = (data.get("artist") or "").strip()
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"found": False}), 400

    match = player_helper.resolve_apple_album(artist, title)
    if not match:
        return jsonify({"found": False})
    return jsonify({"found": True, **match})
