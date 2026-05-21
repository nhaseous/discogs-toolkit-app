from flask import Blueprint, render_template, send_from_directory, current_app
from web_common import is_price_checker_enabled

core_bp = Blueprint('core', __name__)


@core_bp.route('/static/v<version>/<path:filename>')
def versioned_static(version, filename):
    resp = send_from_directory(current_app.static_folder, filename)
    # URL is version-busted, so safe to cache forever
    resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return resp


@core_bp.route('/favicon.ico')
def favicon():
    # Safari requests /favicon.ico directly (ignoring the <link> tag in <head>)
    # and is picky about a PNG-only declaration, so serve the icon here too.
    # Must be cacheable: the HTML is sent no-store, and Safari otherwise won't
    # persist the favicon association for freshly-navigated result URLs.
    resp = send_from_directory(current_app.static_folder, 'logo-64.png', mimetype='image/png')
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp


@core_bp.route("/")
def landingpage():
    return render_template('landing.html',
                           price_checker_enabled=is_price_checker_enabled())
