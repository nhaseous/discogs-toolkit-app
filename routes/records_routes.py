from flask import Blueprint, render_template, session
from helper import records as records_helper

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
    stats = data['stats']
    collection = data['collection']
    inventory  = data['inventory']
    sold       = data['sold']

    col_count = stats['col_count']
    inv_count = stats['inv_count']
    sol_count = stats['sold_count']

    dashboard = records_helper.render_records_dashboard(stats)

    tabs = (
        '<div class="rec-tabs-row">'
        '<div class="rec-tabs">'
        '<button class="rec-tab active" data-tab="collection">Collection ({0})</button>'
        '<button class="rec-tab" data-tab="inventory">Inventory ({1})</button>'
        '<button class="rec-tab" data-tab="sold">Sold ({2})</button>'
        '</div>'
        '</div>'
    ).format(col_count, inv_count, sol_count)

    content = (
        dashboard
        + tabs
        + '<div id="rec-panel-collection" class="rec-panel">' + records_helper.render_col_table(collection) + '</div>'
        + '<div id="rec-panel-inventory" class="rec-panel" style="display:none">' + records_helper.render_inv_table(inventory) + '</div>'
        + '<div id="rec-panel-sold" class="rec-panel" style="display:none">' + records_helper.render_sold_table(sold) + '</div>'
    )

    records_header = (
        '<div class="page-header">'
        '<div class="page-eyebrow">Vault</div>'
        '<h2>My <em>Records</em></h2>'
        '</div>'
    )

    return render_template('records.html',
        content=records_header + content,
        content_class='has-results',
        show_platter=True,
        title='Records'
    )
