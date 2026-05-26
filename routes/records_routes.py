from flask import Blueprint, render_template, session
from services.utils import records as records_helper

records_bp = Blueprint('records', __name__)

_records_data = None


def _get_records_data():
    global _records_data
    if _records_data is None:
        try:
            _records_data = records_helper.load_all()
        except Exception:
            _records_data = records_helper.empty_data()
    return _records_data


@records_bp.route("/records")
def recordspage():
    if session.get('discogs_username') != 'curefortheitch':
        return "Access Denied: You do not have permission to access this page. This feature is restricted to authorized users only.", 403

    data = _get_records_data()

    return render_template('records.html',
        stats=data['stats'],
        collection=data['collection'],
        inventory=data['inventory'],
        sold=data['sold'],
        col_count=data['stats']['col_count'],
        inv_count=data['stats']['inv_count'],
        sol_count=data['stats']['sold_count'],
        content_class='has-results',
        show_platter=True,
        title='Records'
    )
