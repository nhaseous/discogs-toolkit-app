// ==========================================================
// lookup-filters.js — Lookup page filter state + UI:
//   per-tab active filters, item filter helper, filter badge
//   rendering, and the public toggle entry point.
// Calls window._lookupApplyFilter from lookup-pagination.js to
// trigger a re-render, so it must load before lookup-pagination.js
// (pagination's init reads _lookupGetFilteredItems / _lookupActiveFilters).
// ==========================================================

window._lookupActiveFilters = { collection: {}, wantlist: {} };
// Fields where toggling a value should clear any previously-selected value
// on the same field (single-select rather than multi-select). Populated by
// the insights dashboard wiring in lookup.js.
window._exclusiveFilterFields = window._exclusiveFilterFields || {};

function _getActiveLookupTab() {
    var t = document.querySelector('.lookup-tab.active');
    return t ? t.getAttribute('data-tab') : null;
}

window._lookupGetFilteredItems = function(items, tabName) {
    var filters = window._lookupActiveFilters[tabName];
    if (!filters) return items;
    var fields = Object.keys(filters);
    if (!fields.length) return items;
    return items.filter(function(item) {
        for (var fi = 0; fi < fields.length; fi++) {
            var field = fields[fi];
            var vals = filters[field];
            if (!vals || !vals.size) continue;
            var iv = item[field];
            var found;
            if (Array.isArray(iv)) {
                found = true;
                vals.forEach(function(v) { if (iv.indexOf(v) === -1) found = false; });
            } else {
                found = vals.has(String(iv));
            }
            if (!found) return false;
        }
        return true;
    });
};

(function() {
    function _esc(s) { return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
    var _filterBadgesEl = document.getElementById('lookup-filter-badges');

    function _syncFilterBadges() {
        if (!_filterBadgesEl) return;
        _filterBadgesEl.innerHTML = '';
        var tabName = _getActiveLookupTab();
        var filters = window._lookupActiveFilters[tabName];
        if (!filters) return;
        Object.keys(filters).forEach(function(field) {
            filters[field].forEach(function(value) {
                var badge = document.createElement('span');
                badge.className = 'lookup-filter-badge';
                badge.innerHTML = _esc(value) + '<span class="lookup-filter-badge-x">&times;</span>';
                badge.addEventListener('click', function() {
                    if (window._deactivateDashFilter) window._deactivateDashFilter(field, value, tabName);
                    window._toggleLookupFilter(field, value, tabName);
                });
                _filterBadgesEl.appendChild(badge);
            });
        });
    }
    window._syncLookupFilterBadges = _syncFilterBadges;

    window._toggleLookupFilter = function(field, value, tabName) {
        tabName = tabName || _getActiveLookupTab();
        if (tabName !== 'collection' && tabName !== 'wantlist') return;
        var filters = window._lookupActiveFilters[tabName];
        if (!filters[field]) filters[field] = new Set();
        var fset = filters[field];
        if (fset.has(value)) {
            fset.delete(value);
            if (!fset.size) delete filters[field];
        } else {
            if (window._exclusiveFilterFields[field]) fset.clear();
            fset.add(value);
        }
        _syncFilterBadges();
        if (window._lookupApplyFilter) window._lookupApplyFilter(tabName);
    };
})();
