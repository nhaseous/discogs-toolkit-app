// ==========================================================
// matcher.js — Wantlist Matcher "Exact match" toggle. Mirrors the
// Price Checker sort toggle: server renders all (non-exact) matches
// up front, each card/mosaic-item/listing-line tagged with is_exact,
// and toggling switches the displayed view client-side without a
// new search.
// ==========================================================

(function() {
    var toggle = document.getElementById('exact');
    var shell = document.getElementById('matcher-results');
    if (!toggle || !shell) return;

    var grid = document.querySelector('#lookup-panel-matches .match-grid');
    var matchCountEl = document.getElementById('matcher-match-count');
    var tabCountEl = document.getElementById('matcher-tab-count');
    var tabBtn = document.querySelector('.lookup-tab[data-tab="matches"]');
    var exactCount = parseInt(shell.getAttribute('data-exact-count'), 10) || 0;
    var nonexactCount = parseInt(shell.getAttribute('data-nonexact-count'), 10) || 0;

    // Stash the full card set as a flat list, in original (server) order, so
    // we can re-distribute into columns from scratch on each toggle. Cards
    // start out already split into .match-column children by grid.js.
    var allCards = grid ? Array.from(grid.querySelectorAll('.match-card')) : [];

    function rebuildGrid(showOnlyExact) {
        if (!grid) return;
        var visible = showOnlyExact
            ? allCards.filter(function(c) { return c.getAttribute('data-is-exact') === '1'; })
            : allCards;
        // Detach every card before clearing so the nodes survive — grid.innerHTML = ""
        // would otherwise drop them and we'd lose the hidden subset on the next toggle.
        allCards.forEach(function(c) { if (c.parentNode) c.parentNode.removeChild(c); });
        grid.innerHTML = '';
        visible.forEach(function(c) { grid.appendChild(c); });
        if (window._layoutMatchGrids) window._layoutMatchGrids();
    }

    function applyState(showOnlyExact) {
        shell.classList.toggle('matcher-results--exact', showOnlyExact);
        var count = showOnlyExact ? exactCount : nonexactCount;
        if (matchCountEl) matchCountEl.textContent = count;
        if (tabCountEl) tabCountEl.textContent = count;
        if (tabBtn) tabBtn.setAttribute('data-count-text', 'Matches (' + count + ')');
        rebuildGrid(showOnlyExact);
    }

    toggle.addEventListener('change', function() {
        applyState(this.checked);
    });

    // Server always renders the full (non-exact) card set. If the page loaded
    // with exact=yes (toggle pre-checked), filter the grid down to the exact
    // subset now so the grid matches the mosaic/listing CSS filter.
    if (toggle.checked) rebuildGrid(true);
})();
