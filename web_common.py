"""Shared web-layer helpers used across route blueprints.

This module deliberately imports neither ``main`` nor any ``routes`` blueprint so
it can be imported freely from both without creating import cycles.
"""

import os
import sys
import threading
import cloudscraper
from flask import session, request
from requests.auth import AuthBase
from requests_oauthlib import OAuth1 as _OAuth1
from services.utils import auth as auth_persistence

CONSUMER_KEY    = os.environ.get('DISCOGS_CONSUMER_KEY', '')
CONSUMER_SECRET = os.environ.get('DISCOGS_CONSUMER_SECRET', '')
CALLBACK_URL    = os.environ.get('DISCOGS_CALLBACK_URL', 'http://127.0.0.1:8080/callback')

# Static asset cache-busting version
if getattr(sys, 'frozen', False):
    _static_dir = os.path.join(os.environ.get('RESOURCEPATH', os.getcwd()), 'static')
else:
    _static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
GAE_VERSION = os.environ.get('GAE_VERSION', '')


def _compute_static_v():
    try:
        _mtimes = [os.path.getmtime(os.path.join(r, f)) for r, _, fs in os.walk(_static_dir) for f in fs]
        return str(int(max(_mtimes))) if _mtimes else '1'
    except OSError:
        return '1'


if GAE_VERSION:
    STATIC_V = GAE_VERSION
else:
    STATIC_V = _compute_static_v()


def current_static_v():
    # On GAE / frozen builds, the static tree is immutable — use the cached value.
    # In local dev, recompute so JS/CSS edits bust the cache without a server restart.
    if GAE_VERSION or getattr(sys, 'frozen', False):
        return STATIC_V
    return _compute_static_v()


def load_persistent_auth():
    if not session.get('discogs_username') and auth_persistence.is_macos_dist():
        data = auth_persistence.get_from_keychain()
        if data:
            session.permanent = True
            session['discogs_access_token']  = data.get('access_token')
            session['discogs_access_secret'] = data.get('access_secret')
            session['discogs_username']      = data.get('username')
            session['discogs_avatar']        = data.get('avatar_url', '')
    elif session.get('discogs_username') and not session.permanent:
        session.permanent = True


class DiscogsAppAuth(AuthBase):
    """App-level Discogs auth: identifies the *application* via consumer
    key/secret with no user token, by setting the ``Authorization: Discogs
    key=..., secret=...`` header Discogs documents for app authentication.

    This is the fallback for signed-out visitors. It carries no user identity
    (so it can't read private data or write), but it lifts the request from
    Discogs' unauthenticated 25/min tier to the authenticated 60/min tier — the
    same ceiling a signed-in user gets. It's a plain ``requests`` auth callable,
    interchangeable with the ``OAuth1`` object used for signed-in users, so every
    downstream caller that already accepts ``auth=`` works unchanged.
    """
    def __call__(self, r):
        if CONSUMER_KEY and CONSUMER_SECRET:
            r.headers['Authorization'] = 'Discogs key={0}, secret={1}'.format(
                CONSUMER_KEY, CONSUMER_SECRET)
        return r


def oauth_auth():
    # Signed in: authenticate as the user (consumer key/secret + their token).
    if session.get('discogs_access_token'):
        return _OAuth1(CONSUMER_KEY, CONSUMER_SECRET,
                       session['discogs_access_token'],
                       session['discogs_access_secret'])
    # Signed out: authenticate as the application so requests still get the
    # 60/min authenticated rate limit instead of the 25/min unauthenticated one.
    return DiscogsAppAuth()


def is_price_checker_enabled():
    is_gae = os.environ.get('GAE_ENV', '').startswith('standard')
    is_local = request.host.startswith('127.0.0.1') or request.host.startswith('localhost')
    is_frozen = getattr(sys, 'frozen', False)
    # Price Checker is disabled on GAE, enabled on local dev and macOS dist.
    if is_gae:
        return False
    return is_frozen or is_local


# A single long-lived cloudscraper shared across all Price Checker scrape
# requests. Cloudflare clearance (the cf_clearance cookie) is solved once and
# reused for every release, instead of re-solving on each batch — repeatedly
# negotiating Cloudflare from one IP is what triggers blocks. This restores the
# original behaviour where one scraper served the whole inventory scrape.
_pc_scraper = None
_pc_scraper_lock = threading.Lock()


def get_pc_scraper():
    global _pc_scraper
    if _pc_scraper is None:
        with _pc_scraper_lock:
            if _pc_scraper is None:
                _pc_scraper = cloudscraper.create_scraper(
                    browser={'browser': 'chrome', 'platform': 'android', 'desktop': False})
    return _pc_scraper
