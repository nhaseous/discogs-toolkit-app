// ==========================================================
// lookup-browse.js — Lookup page browsing behavior:
//   filter state + scroll helper, tab/mosaic switching,
//   pagination + card rendering + filter badges, expand toggle.
// Calls window._layoutMatchGrids / window._resetMatchCardHover
// from grid.js, so it must load after grid.js (and before lookup.js,
// which uses the window globals defined here).
// ==========================================================

var _lookupActiveFilters = { collection: {}, wantlist: {} };
function _getActiveLookupTab() {
    var t = document.querySelector('.lookup-tab.active');
    return t ? t.getAttribute('data-tab') : null;
}
function _lookupGetFilteredItems(items, tabName) {
    var filters = _lookupActiveFilters[tabName];
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
}

function _withLookupScroll(action) {
    ToolkitUtils.withScrollGuard(action, ".lookup-tabs-row");
}

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
        _withLookupScroll(function() { doTabSwitch(tab.getAttribute("data-tab")); });
    });
    window._switchToTab = function(target) {
        _withLookupScroll(function() { doTabSwitch(target); });
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
    var PAGE_SIZE = 50;
    var pagTabs = document.querySelectorAll(".lookup-tab");
    if (!pagTabs.length) return;
    var pagEl = document.getElementById("lookup-pagination");
    var prevBtn = document.getElementById("pag-prev");
    var nextBtn = document.getElementById("pag-next");
    var labelEl = document.getElementById("pag-label");
    var sizeBtn = document.getElementById("pag-size-btn");
    var sizeMenu = document.getElementById("pag-size-menu");
    var sizeValEl = document.getElementById("pag-size-val");
    var sizeOpts = sizeMenu ? Array.from(sizeMenu.querySelectorAll(".pag-select-opt")) : [];

    var VINYL_SVG = '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="46" fill="currentColor"/><circle cx="50" cy="50" r="20" fill="var(--rule)"/><circle cx="50" cy="50" r="4" fill="currentColor"/></svg>';
    function _esc(s) { return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
    function renderLookupCard(m, showStats) {
        var imgSrc = m.cover_image || m.thumb;
        var art = imgSrc
            ? '<img src="' + _esc(imgSrc) + '" alt="" loading="lazy" class="match-card-img">'
            : '<div class="match-card-placeholder">' + VINYL_SVG + '</div>';
        var info = '<div class="match-card-artist">' + _esc(Array.isArray(m.artist) ? m.artist.join(' / ') : (m.artist || '')) + '</div>'
            + '<div class="match-card-title">' + _esc(m.title) + '</div>';
        var body = (m.format && m.format.length ? '<div class="match-card-format">' + _esc(m.format.join(' / ')) + '</div>' : '')
            + (m.format_descriptions ? '<div class="match-card-format-desc">' + _esc(m.format_descriptions) + '</div>' : '')
            + (m.format_text ? '<div class="match-card-format-text">' + _esc(m.format_text) + '</div>' : '')
            + (m.for_sale && m.for_sale_url ? '<div class="match-card-forsale" data-href="' + _esc(m.for_sale_url) + '" onclick="event.stopPropagation();event.preventDefault();window.open(this.dataset.href,\'_blank\',\'noopener,noreferrer\')">' + _esc(m.for_sale) + '</div>' : '')
            + (m.comment ? '<div class="match-card-comment">' + _esc(m.comment) + '</div>' : '')
            + (showStats && m.stats ? '<div class="match-card-stats">' + _esc(m.stats) + '</div>' : '');
        return '<a href="' + _esc(m.url || '#') + '" class="match-card" target="_blank" rel="noopener noreferrer">'
            + '<div class="match-card-art">' + art + '</div>'
            + '<div class="match-card-info">' + info + '</div>'
            + '<div class="match-card-body">' + body + '</div>'
            + '</a>';
    }

    var state = {};
    var _rerenderRaf = 0;
    function getGrid(tabName) {
        var panel = document.getElementById("lookup-panel-" + tabName);
        return panel ? panel.querySelector(".match-grid") : null;
    }
    pagTabs.forEach(function(tab) {
        var name = tab.getAttribute("data-tab");
        var grid = getGrid(name);
        var backCard = grid ? grid.querySelector(".match-card--back") : null;
        var dataEl = document.querySelector('.lookup-data[data-tab="' + name + '"]');
        var items = null, cards = null, showStats = false;
        var totalItems = 0, needsHydration = false, deferred = false;
        if (dataEl) {
            items = JSON.parse(dataEl.textContent);
            showStats = dataEl.getAttribute("data-show-stats") === "1";
            // data-total reflects the full server-side count (not just the inlined
            // first page), so pagination math reports the real "page N of M" even
            // before /lookup/data hydration completes.
            var declaredTotal = parseInt(dataEl.getAttribute("data-total"), 10);
            totalItems = isNaN(declaredTotal) ? items.length : declaredTotal;
            needsHydration = dataEl.getAttribute("data-needs-hydration") === "1";
            // Deferred tabs ship with no items at all — first activation fetches
            // them from /lookup/load-tab. Different from needsHydration (which
            // means "we have the first page; fetch the rest").
            deferred = dataEl.getAttribute("data-deferred") === "1";
        } else {
            cards = grid ? Array.from(grid.querySelectorAll(".match-card:not(.match-card--back)")) : [];
            totalItems = cards ? cards.length : 0;
        }
        var total = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));
        state[name] = {
            page: 1, total: total, items: items, cards: cards,
            showStats: showStats, backCard: backCard, ready: false,
            needsHydration: needsHydration, totalItems: totalItems,
            deferred: deferred,
        };
    });

    // Deferred load: when the page was opened with a list_id, collection and
    // wantlist start with no items at all. First tab activation fetches the
    // items + insights HTML in a single call to /lookup/load-tab.
    var _loadPromises = {};
    function _loadDeferredTab(tabName) {
        var s = state[tabName];
        if (!s || !s.deferred) return Promise.resolve(s ? s.items : null);
        if (_loadPromises[tabName]) return _loadPromises[tabName];

        var qs = new URLSearchParams(window.location.search);
        var username = qs.get('username') || '';
        
        var p = ToolkitAPI.loadLookupTab(username, tabName)
            .then(function(data) {
                var items = (data && data.items) || [];
                s.items = items;
                s.totalItems = items.length;
                s.total = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
                s.deferred = false;
                s.ready = false;

                if (data && data.insights_html) {
                    _injectInsights(tabName, data.insights_html);
                }
                if (window._onTabHydrated) window._onTabHydrated(tabName);
                return items;
            })
            .catch(function() {
                _loadPromises[tabName] = null;
                return s.items || [];
            });
        _loadPromises[tabName] = p;
        return p;
    }

    function _injectInsights(tabName, html) {
        var existingId = tabName === 'wantlist' ? 'wantlist-insights-dash' : 'collection-insights-dash';
        if (document.getElementById(existingId)) return;
        var anchor = document.querySelector('.lookup-mosaic-wrap');
        if (!anchor || !anchor.parentNode) return;
        // Collection dashboard goes above the mosaic; wantlist sits after the
        // collection dashboard (matching the server-side ordering).
        if (tabName === 'collection') {
            anchor.insertAdjacentHTML('beforebegin', html);
        } else {
            var collDash = document.getElementById('collection-insights-dash');
            (collDash || anchor).insertAdjacentHTML(collDash ? 'afterend' : 'beforebegin', html);
        }
        if (window._registerLookupDash) window._registerLookupDash(tabName);
    }
    window._lookupLoadDeferredTab = _loadDeferredTab;

    // Lazy hydration: pull the full items array from /lookup/data after first
    // paint so the initial HTML stays small. Until each tab finishes hydrating,
    // pagination beyond page 1 and filter interactions wait on its promise.
    var _hydrationPromises = {};
    function _hydrateTab(tabName) {
        var s = state[tabName];
        if (!s || !s.needsHydration) return Promise.resolve(s ? s.items : null);
        if (_hydrationPromises[tabName]) return _hydrationPromises[tabName];
        var qs = new URLSearchParams(window.location.search);
        var username = qs.get('username') || '';
        var listId = qs.get('list_id') || '';

        var p = ToolkitAPI.getLookupData(username, tabName, listId)
            .then(function(data) {
                var fullItems = (data && data.items) || null;
                if (fullItems && fullItems.length >= s.items.length) {
                    s.items = fullItems;
                    s.totalItems = fullItems.length;
                    s.total = Math.max(1, Math.ceil(fullItems.length / PAGE_SIZE));
                    s.needsHydration = false;
                    if (window._onTabHydrated) window._onTabHydrated(tabName);
                }
                return s.items;
            })
            .catch(function() {
                // 410 (cache expired) or network error — keep the inline subset;
                // the user can refresh to get a fresh lookup. Clear the cached
                // promise so a later interaction can retry.
                _hydrationPromises[tabName] = null;
                s.needsHydration = false;
                return s.items;
            });
        _hydrationPromises[tabName] = p;
        return p;
    }
    window._lookupHydrateTab = _hydrateTab;
    function syncControls(tabName) {
        if (!pagEl || !labelEl) return;
        var s = state[tabName];
        if (!s) return;
        pagEl.style.visibility = "";
        labelEl.textContent = s.page + " / " + s.total;
        prevBtn.disabled = s.page <= 1;
        nextBtn.disabled = s.page >= s.total;
    }
    function applyPage(tabName, page) {
        var s = state[tabName];
        if (!s) return;
        s.page = page;
        s.ready = true;
        var grid = getGrid(tabName);
        if (!grid) return;
        var start = (page - 1) * PAGE_SIZE;
        if (s.items) {
            var sourceItems = (tabName === 'collection' || tabName === 'wantlist')
                ? _lookupGetFilteredItems(s.items, tabName) : s.items;
            s.total = Math.max(1, Math.ceil(sourceItems.length / PAGE_SIZE));
            var pageItems = sourceItems.slice(start, start + PAGE_SIZE);
            var html = '';
            pageItems.forEach(function(m) { html += renderLookupCard(m, s.showStats); });
            grid.innerHTML = html;
            if (s.backCard) grid.insertBefore(s.backCard, grid.firstChild);
        } else {
            var pageCards = s.cards.slice(start, start + PAGE_SIZE);
            grid.innerHTML = '';
            if (s.backCard) grid.appendChild(s.backCard);
            pageCards.forEach(function(c) { grid.appendChild(c); });
        }
    }
    var _tabLabels = { collection: 'Collection', wantlist: 'Wantlist' };
    function _syncTabCount(tabName, s) {
        var filters = _lookupActiveFilters[tabName] || {};
        var isFiltered = Object.keys(filters).length > 0;
        var total = s.items.length;
        var filtered = isFiltered ? _lookupGetFilteredItems(s.items, tabName).length : total;
        var tabEl = document.querySelector('.lookup-tab[data-tab="' + tabName + '"]');
        if (!tabEl) return;
        // Lock width on first filter so the button doesn't resize
        if (!tabEl._lockedWidth) {
            tabEl.style.minWidth = tabEl.offsetWidth + 'px';
            tabEl._lockedWidth = true;
        }
        tabEl.textContent = (_tabLabels[tabName] || tabName) + ' (' + filtered + ')';
        var countLabel = isFiltered ? 'Selected' : (_tabLabels[tabName] || tabName);
        var countText = countLabel + ': ' + filtered + ' item' + (filtered !== 1 ? 's' : '');
        tabEl.setAttribute('data-count-text', countText);
        var countEl = document.getElementById('lookup-count');
        if (countEl && tabEl.classList.contains('active')) {
            countEl.textContent = countText;
        }
        // Release width lock when filters are cleared
        if (!isFiltered) {
            tabEl.style.minWidth = '';
            tabEl._lockedWidth = false;
        }
    }
    var _exclusiveFilterFields = window._exclusiveFilterFields = {};
    var _filterBadgesEl = document.getElementById('lookup-filter-badges');
    function _syncFilterBadges() {
        if (!_filterBadgesEl) return;
        _filterBadgesEl.innerHTML = '';
        var tabName = _getActiveLookupTab();
        var filters = _lookupActiveFilters[tabName];
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
        var filters = _lookupActiveFilters[tabName];
        if (!filters[field]) filters[field] = new Set();
        var fset = filters[field];
        if (fset.has(value)) {
            fset.delete(value);
            if (!fset.size) delete filters[field];
        } else {
            if (_exclusiveFilterFields[field]) fset.clear();
            fset.add(value);
        }
        _syncFilterBadges();
        var s = state[tabName];
        if (!s || !s.items) return;
        var rerender = function() {
            applyPage(tabName, 1);
            syncControls(tabName);
            _syncTabCount(tabName, s);
            if (window._layoutMatchGrids) window._layoutMatchGrids();
        };
        // Defer the grid rebuild one frame so the click's visual feedback —
        // active class on the dashboard row, pie/line dimming via :has(),
        // filter badge appearing/disappearing — paints immediately. The grid
        // (rebuild 50 cards + reflow into columns + equalize) is the slow part
        // (~30–50ms on a sizeable collection); running it inline blocks the
        // browser from painting the cheap visual updates until it finishes.
        // Coalesce rapid toggles so multiple clicks don't queue redundant
        // rerenders against the same final filter state.
        if (_rerenderRaf) cancelAnimationFrame(_rerenderRaf);
        _rerenderRaf = requestAnimationFrame(function() {
            _rerenderRaf = 0;
            rerender();
        });
        // Filters need the complete item list to compute counts and match
        // across pages. The deferred rerender above gives instant feedback
        // against the inline subset; this second pass replaces it with the
        // full data when hydration lands.
        if (s.needsHydration) _hydrateTab(tabName).then(rerender);
    };
    window._applyTabPage = function(tabName) {
        var s = state[tabName];
        if (!s) return;
        // Deferred tab: kick off the fetch and show an empty page until it lands.
        // _onTabHydrated re-runs applyPage once the items arrive.
        if (s.deferred) {
            if (prevBtn) prevBtn.disabled = true;
            if (nextBtn) nextBtn.disabled = true;
            _loadDeferredTab(tabName);
            return;
        }
        if (!s.ready) applyPage(tabName, 1);
        syncControls(tabName);
    };
    window._registerAndApplyTab = function(tabName, items, showStats) {
        var total = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
        state[tabName] = { page: 1, total: total, items: items, cards: null, showStats: showStats, backCard: null, ready: false };
        applyPage(tabName, 1);
        syncControls(tabName);
        if (window._layoutMatchGrids) window._layoutMatchGrids();
    };
    // Only paginate the active tab on initial load — hidden tabs (wantlist, lists)
    // get their first applyPage() lazily on tab activation via _applyTabPage().
    // Saves the HTML build + DOM insertion for ~50 cards in tabs the user may never open.
    var initTab = document.querySelector(".lookup-tab.active");
    if (initTab) {
        var initName = initTab.getAttribute("data-tab");
        applyPage(initName, 1);
        syncControls(initName);
        if (window._layoutMatchGrids) window._layoutMatchGrids();
    }

    // Populates an initially-empty mosaic (wantlist/list) from the current
    // state.items. Called when the user first activates the tab and again
    // when /lookup/data hydration completes with the full item list.
    function _populateMosaic(tabName) {
        var mosaic = document.getElementById('lookup-mosaic-' + tabName);
        if (!mosaic) return;
        if (mosaic.dataset.populated === '1') return;
        var s = state[tabName];
        if (!s || !s.items) return;
        // Skip while the tab is still waiting on its initial load — items is the
        // empty placeholder array at this point. _onTabHydrated re-runs once the
        // real items land.
        if (s.deferred) return;
        Mosaic.populate(mosaic, s.items, { tag: tabName === 'list' ? 'span' : 'a' });
        if (!s.needsHydration) mosaic.dataset.populated = '1';
    }
    window._populateLookupMosaic = _populateMosaic;

    // When a tab finishes hydrating, refresh anything that was rendered against
    // the inline subset: the page counter, the tab label count, and the mosaic.
    // For deferred tabs (no inline subset at all), render the first page now.
    window._onTabHydrated = function(tabName) {
        var s = state[tabName];
        if (!s) return;
        if (!s.ready && document.querySelector('.lookup-tab.active[data-tab="' + tabName + '"]')) {
            applyPage(tabName, 1);
        }
        _syncTabCount(tabName, s);
        syncControls(tabName);
        var mosaic = document.getElementById('lookup-mosaic-' + tabName);
        if (mosaic && mosaic.dataset.populated !== '1') _populateMosaic(tabName);
        if (window._layoutMatchGrids) window._layoutMatchGrids();
    };

    // Kick off hydration for every tab that still has trimmed inline data.
    // requestIdleCallback runs after first paint so the user sees the
    // first-page cards immediately; the heavy JSON fetch streams in behind.
    // Deferred tabs are skipped — they only load on explicit user activation.
    function _kickoffHydration() {
        Object.keys(state).forEach(function(name) {
            if (state[name] && state[name].needsHydration && !state[name].deferred) _hydrateTab(name);
        });
    }
    if (window.requestIdleCallback) {
        requestIdleCallback(_kickoffHydration, { timeout: 1500 });
    } else {
        setTimeout(_kickoffHydration, 100);
    }
    function getActiveTab() {
        var a = document.querySelector(".lookup-tab.active");
        return a ? a.getAttribute("data-tab") : null;
    }
    function _goToPage(name, target) {
        var s = state[name];
        if (!s) return;
        var doRender = function() {
            _withLookupScroll(function() {
                applyPage(name, target);
                syncControls(name);
                if (window._layoutMatchGrids) window._layoutMatchGrids();
            });
        };
        // Hydration brings in items beyond the inline first page — wait for it
        // before paginating past page 1 so we don't show a half-filled grid.
        if (s.deferred) {
            if (prevBtn) prevBtn.disabled = true;
            if (nextBtn) nextBtn.disabled = true;
            _loadDeferredTab(name).then(doRender);
        } else if (s.needsHydration && target > 1) {
            if (prevBtn) prevBtn.disabled = true;
            if (nextBtn) nextBtn.disabled = true;
            _hydrateTab(name).then(doRender);
        } else {
            doRender();
        }
    }
    if (prevBtn) prevBtn.addEventListener("click", function() {
        var name = getActiveTab();
        var s = state[name];
        if (s && s.page > 1) _goToPage(name, s.page - 1);
    });
    if (nextBtn) nextBtn.addEventListener("click", function() {
        var name = getActiveTab();
        var s = state[name];
        if (s && s.page < s.total) _goToPage(name, s.page + 1);
    });
    function applySize(value) {
        PAGE_SIZE = value;
        if (sizeValEl) sizeValEl.textContent = value;
        sizeOpts.forEach(function(o) {
            o.classList.toggle("pag-select-opt--active", parseInt(o.getAttribute("data-value"), 10) === value);
        });
        if (sizeMenu) sizeMenu.style.display = "none";
        var activeName = getActiveTab();
        for (var n in state) {
            var s = state[n], count = s.items ? s.items.length : (s.cards ? s.cards.length : 0);
            s.total = Math.max(1, Math.ceil(count / PAGE_SIZE));
            state[n].page = 1;
            if (n !== activeName) state[n].ready = false;
        }
        if (activeName) {
            _withLookupScroll(function() {
                applyPage(activeName, 1);
                syncControls(activeName);
                if (window._layoutMatchGrids) window._layoutMatchGrids();
            });
        }
    }
    if (sizeBtn) sizeBtn.addEventListener("click", function(e) {
        e.stopPropagation();
        if (sizeMenu) sizeMenu.style.display = sizeMenu.style.display === "block" ? "none" : "block";
    });
    sizeOpts.forEach(function(opt) {
        opt.addEventListener("click", function() {
            applySize(parseInt(this.getAttribute("data-value"), 10));
        });
    });
    document.addEventListener("click", function(e) {
        if (sizeMenu && sizeMenu.style.display === "block") {
            var wrap = document.getElementById("pag-size-wrap");
            if (wrap && !wrap.contains(e.target)) sizeMenu.style.display = "none";
        }
    });
})();

(function() {
    var btn = document.getElementById("pag-expand-btn");
    if (!btn) return;
    btn.addEventListener("click", function() {
        var on = this.classList.toggle("active");
        _withLookupScroll(function() {
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
