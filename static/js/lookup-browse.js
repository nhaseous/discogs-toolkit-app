// ==========================================================
// lookup-browse.js — Lookup page orchestration: scroll-anchored
//   tab/mosaic switching and the "expand all cards" toggle.
// Filter state + UI lives in lookup-filters.js; pagination,
// hydration, and card rendering live in lookup-pagination.js.
// Calls window._layoutMatchGrids / window._resetMatchCardHover
// from grid.js, so it must load after grid.js.
// ==========================================================

window._withLookupScroll = function(action) {
    ToolkitUtils.withScrollGuard(action, ".lookup-tabs-row");
};

(function() {
    var tabsContainer = document.querySelector(".lookup-tabs");
    if (!tabsContainer || !tabsContainer.querySelector(".lookup-tab")) return;

    // True when the user's session originated from a specific user list (either
    // the page loaded with list_id in the URL, or the user opened a list via AJAX).
    // When true, clicking Collection or Wantlist redirects to the URL without
    // list_id so those tabs load cleanly without the (expensive) list items.
    var _listEntryActive = (new URLSearchParams(window.location.search)).has('list_id');
    window._markListEntry = function() { _listEntryActive = true; };

    function switchMosaics(target) {
        // Lazy mosaics: wantlist + list ship empty in the HTML. Populate the
        // incoming mosaic from its tab's item list right before the animation
        // starts so the cards slide in fully composed.
        if (window._populateLookupMosaic) window._populateLookupMosaic(target);

        var all = Array.from(document.querySelectorAll(".lookup-mosaic"));
        var incoming = document.getElementById("lookup-mosaic-" + target);
        var outgoing = all.find(function(m) { return m !== incoming && !m.classList.contains("lookup-mosaic--inactive"); });
        Mosaic.switchMosaics({
            incoming: incoming,
            outgoing: outgoing,
            wrap: document.querySelector(".lookup-mosaic-wrap"),
            inactiveClass: "lookup-mosaic--inactive",
        });
    }
    var countEl = document.getElementById("lookup-count");
    function setCountEl(el, text, url) {
        if (!el) return;
        if (url) {
            el.innerHTML = '<a href="' + url + '" target="_blank" rel="noopener noreferrer" class="meta-user-link">' + text + '</a>';
        } else {
            el.textContent = text;
        }
    }
    function doTabSwitch(target) {
        if (_listEntryActive && (target === 'collection' || target === 'wantlist')) {
            var params = new URLSearchParams(window.location.search);
            params.delete('list_id');
            var cleanUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
            window.location.replace(cleanUrl);
            return;
        }
        var countText = '', countUrl = '';
        document.querySelectorAll(".lookup-tab").forEach(function(t) {
            var isTarget = t.getAttribute("data-tab") === target;
            t.classList.toggle("active", isTarget);
            if (isTarget) {
                countText = t.getAttribute("data-count-text") || '';
                countUrl = t.getAttribute("data-count-url") || '';
            }
        });
        document.querySelectorAll(".lookup-panel").forEach(function(panel) {
            panel.style.display = panel.id === "lookup-panel-" + target ? "" : "none";
        });
        switchMosaics(target);
        if (countText) setCountEl(countEl, countText, countUrl);
        if (window._resetMatchCardHover) window._resetMatchCardHover();
        if (window._applyTabPage) window._applyTabPage(target);
        if (window._layoutMatchGrids) window._layoutMatchGrids();
        if (window._onLookupTabChange) window._onLookupTabChange(target);
    }
    tabsContainer.addEventListener("click", function(e) {
        var tab = e.target.closest(".lookup-tab");
        if (!tab) return;
        window._withLookupScroll(function() { doTabSwitch(tab.getAttribute("data-tab")); });
    });
    window._switchToTab = function(target) {
        window._withLookupScroll(function() { doTabSwitch(target); });
    };
    var initTab = document.querySelector(".lookup-tab.active");
    if (initTab) setCountEl(countEl, initTab.getAttribute("data-count-text") || '', initTab.getAttribute("data-count-url") || '');
    if (initTab) {
        var initName = initTab.getAttribute("data-tab");
        document.querySelectorAll(".lookup-panel").forEach(function(panel) {
            panel.style.display = panel.id === "lookup-panel-" + initName ? "" : "none";
        });
    }
})();

(function() {
    var btn = document.getElementById("pag-expand-btn");
    if (!btn) return;
    btn.addEventListener("click", function() {
        var on = this.classList.toggle("active");
        window._withLookupScroll(function() {
            document.querySelectorAll(".match-grid").forEach(function(g) {
                g.classList.toggle("match-grid--expanded", on);
            });
        });
        // Re-run layout once the body expand/collapse transition (~0.28s) ends,
        // then watch cards for any further size shifts over a short window
        // (lazy images / web fonts settling). Observing CARDS — not the grid —
        // means our inline marginBottom writes, which sit outside the card box,
        // don't retrigger the observer.
        var relayout = function() { if (window._layoutMatchGrids) window._layoutMatchGrids(); };
        var grid = Array.from(document.querySelectorAll(".match-grid")).find(function(g) { return g.offsetParent; });
        if (!grid) return;
        var startFollowup = function() {
            relayout();
            if (!window.ResizeObserver) return;
            var roTimer = null;
            var firstFire = true;
            var ro = new ResizeObserver(function() {
                // Skip the synthetic fire ResizeObserver emits at observe() time.
                if (firstFire) { firstFire = false; return; }
                clearTimeout(roTimer);
                roTimer = setTimeout(relayout, 80);
            });
            grid.querySelectorAll('.match-card:not(.match-card--back)').forEach(function(c) { ro.observe(c); });
            setTimeout(function() { ro.disconnect(); clearTimeout(roTimer); }, 1200);
        };
        var firstBody = grid.querySelector('.match-card-body');
        if (!firstBody) { startFollowup(); return; }
        var triggered = false;
        var fire = function() {
            if (triggered) return;
            triggered = true;
            firstBody.removeEventListener('transitionend', onEnd);
            startFollowup();
        };
        var onEnd = function(e) { if (e.propertyName === 'max-height') fire(); };
        firstBody.addEventListener('transitionend', onEnd);
        // Safety net: if transitionend doesn't fire (browser quirk, hidden tab),
        // still start the followup. 500ms covers the 280ms transition + slack.
        setTimeout(fire, 500);
    });
})();
