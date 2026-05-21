import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google")
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

from dotenv import load_dotenv
load_dotenv()

import os
import sys
from datetime import timedelta
from flask import Flask, session
import assets
from helper import pricechecker
import web_common
from routes import register_blueprints

if getattr(sys, 'frozen', False):
    app = Flask(__name__, template_folder=os.path.join(os.environ.get('RESOURCEPATH', os.getcwd()), 'templates'), static_folder=os.path.join(os.environ.get('RESOURCEPATH', os.getcwd()), 'static'))
else:
    app = Flask(__name__)
app.config['SECRET_KEY']              = os.environ.get('FLASK_SECRET_KEY', '')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE']   = os.environ.get('GAE_ENV', '').startswith('standard')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=90)


@app.after_request
def _no_cache_html(resp):
    # Prevent browsers from caching HTML — ensures they always re-fetch
    # the page and pick up the latest versioned static URLs after a deploy.
    if resp.mimetype == 'text/html':
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
    return resp


@app.before_request
def _load_persistent_auth():
    web_common.load_persistent_auth()


@app.context_processor
def _inject_globals():
    def _total_int(e):
        try: return int(str(e.total).replace(',', '').strip())
        except (ValueError, TypeError): return None

    def get_inventory_stats(inventory_list):
        return {
            'recent': sum(1 for e in inventory_list if e and e.daysAgo is not None),
            'old': sum(1 for e in inventory_list if e and getattr(e, 'yearsAgo', None) is not None),
            'low': sum(1 for e in inventory_list if e and _total_int(e) is not None and (_total_int(e) or 0) < 4),
            'lowest': sum(1 for e in inventory_list if e and _total_int(e) == 1),
            'high': sum(1 for e in inventory_list if e and _total_int(e) is not None and (_total_int(e) or 0) > 4),
            'highest': sum(1 for e in inventory_list if e and _total_int(e) is not None and (_total_int(e) or 0) > 9),
            'cheapest': sum(1 for e in inventory_list if e and 'card-cheapest-badge' in getattr(e, 'price_badges', '')),
            'overpriced': sum(1 for e in inventory_list if e and 'card-overpriced-badge' in getattr(e, 'price_badges', '')),
        }

    return {
        'logo_svg': assets.LOGO_SVG,
        'discogs_logo_svg': assets.DISCOGS_LOGO_SVG,
        'vinyl_placeholder_svg': assets.VINYL_PLACEHOLDER_SVG,
        'search_icon_svg': assets.SEARCH_ICON_SVG,
        'back_arrow_svg': assets.BACK_ARROW_SVG,
        'eye_closed_svg': assets.EYE_CLOSED_SVG,
        'eye_open_svg': assets.EYE_OPEN_SVG,
        'rate_limit_notice': assets.RATE_LIMIT_NOTICE,
        'cloudflare_notice': assets.CLOUDFLARE_NOTICE,
        'session_user': session.get('discogs_username'),
        'session_avatar': session.get('discogs_avatar', ''),
        'price_checker_enabled': web_common.is_price_checker_enabled(),
        'is_frozen': getattr(sys, 'frozen', False),
        'static_v': web_common.current_static_v(),
        'entry_badges': pricechecker._entry_badges,
        'get_inventory_stats': get_inventory_stats,
    }


@app.template_filter('ordinal')
def ordinal_filter(n):
    return pricechecker.ordinal(n)


register_blueprints(app)


## Local Testing ##

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True, threaded=True)
