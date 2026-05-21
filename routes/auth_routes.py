from flask import Blueprint, request, session, redirect
import discogs_client as _discogs_client
from web_common import CONSUMER_KEY, CONSUMER_SECRET, CALLBACK_URL
from helper import auth as auth_persistence

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login')
def login():
    d = _discogs_client.Client('DiscogsToolkit/1.0',
        consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET)
    token, secret, url = d.get_authorize_url(callback_url=CALLBACK_URL)
    session['oauth_token']  = token
    session['oauth_secret'] = secret
    return redirect(url)


@auth_bp.route('/callback')
def oauth_callback():
    oauth_verifier = request.args.get('oauth_verifier')
    if not oauth_verifier:
        return redirect('/')
    d = _discogs_client.Client('DiscogsToolkit/1.0',
        consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET)
    d.set_token(session.pop('oauth_token', ''), session.pop('oauth_secret', ''))
    try:
        access_token, access_secret = d.get_access_token(oauth_verifier)
        me = d.identity()
        username = me.username
        try:
            avatar_url = d.user(username).data.get('avatar_url', '') or ''
        except Exception:
            avatar_url = ''
        session['discogs_access_token']  = access_token
        session['discogs_access_secret'] = access_secret
        session['discogs_username']      = username
        session['discogs_avatar']        = avatar_url
        session.permanent = True
        if auth_persistence.is_macos_dist():
            auth_persistence.save_to_keychain(username, access_token, access_secret, avatar_url)
    except Exception:
        pass
    return redirect('/')


@auth_bp.route('/logout')
def logout():
    session.clear()
    if auth_persistence.is_macos_dist():
        auth_persistence.delete_from_keychain()
    return redirect(request.referrer or '/')
