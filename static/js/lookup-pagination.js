// ==========================================================
// lookup-pagination.js — Lookup page pagination + per-tab data
//   lifecycle: card rendering, page state, deferred-load + lazy
//   hydration, mosaic population, prev/next/page-size controls,
//   and the filter-driven rerender entry point.
// Reads window._lookupActiveFilters / window._lookupGetFilteredItems
// from lookup-filters.js, so it must load after lookup-filters.js.
// Calls window._withLookupScroll from lookup-browse.js (registered
// before user interaction, so cross-file load order is flexible).
// ==========================================================

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
    var PLAY_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z" fill="currentColor"/></svg>';
    function _esc(s) { return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
    function renderLookupCard(m, showStats) {
        var imgSrc = m.cover_image || m.thumb;
        var art = imgSrc
            ? '<img src="' + _esc(imgSrc) + '" alt="" loading="lazy" class="match-card-img">'
            : '<div class="match-card-placeholder">' + VINYL_SVG + '</div>';
        var info = '<div class="match-card-artist">' + _esc(Array.isArray(m.artist) ? m.artist.join(' / ') : (m.artist || '')) + '</div>'
            + '<div class="match-card-title">' + _esc(m.title) + '</div>';
        // The play button is right-aligned inside whichever row hosts it, and the
        // row sits inside the hover-revealed card body so the button shows on
        // hover/expand. data-artist carries the primary artist only (extra/featured
        // artists hurt the Apple Music match).
        var primaryArtist = Array.isArray(m.artist) ? (m.artist[0] || '') : (m.artist || '');
        var playBtn = '<button type="button" class="match-card-play" data-artist="' + _esc(primaryArtist) + '" data-title="' + _esc(m.title) + '" title="Play preview on Apple Music" aria-label="Play preview on Apple Music">' + PLAY_SVG + '</button>';
        var hasFormat = m.format && m.format.length;
        // Cards with a format (collection / wantlist) host the button in the format
        // row. List cards have no format, so it rides the for-sale row instead —
        // and when the item has no for-sale info we still render an empty for-sale
        // field so the button has a home (the empty field stays invisible).
        var formatRow = hasFormat
            ? '<div class="match-card-format"><span class="match-card-format-label">' + _esc(m.format.join(' / ')) + '</span>' + playBtn + '</div>'
            : '';
        var forsaleRow = '';
        if (m.for_sale && m.for_sale_url) {
            forsaleRow = '<div class="match-card-forsale" data-href="' + _esc(m.for_sale_url) + '" onclick="event.stopPropagation();event.preventDefault();window.open(this.dataset.href,\'_blank\',\'noopener,noreferrer\')">'
                + '<span class="match-card-forsale-label">' + _esc(m.for_sale) + '</span>'
                + (hasFormat ? '' : playBtn)
                + '</div>';
        } else if (!hasFormat) {
            forsaleRow = '<div class="match-card-forsale match-card-forsale--empty"><span class="match-card-forsale-label"></span>' + playBtn + '</div>';
        }
        var body = formatRow
            + (m.format_descriptions ? '<div class="match-card-format-desc">' + _esc(m.format_descriptions) + '</div>' : '')
            + (m.format_text ? '<div class="match-card-format-text">' + _esc(m.format_text) + '</div>' : '')
            + forsaleRow
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
                ? window._lookupGetFilteredItems(s.items, tabName) : s.items;
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
        var filters = window._lookupActiveFilters[tabName] || {};
        var isFiltered = Object.keys(filters).length > 0;
        var total = s.items.length;
        var filtered = isFiltered ? window._lookupGetFilteredItems(s.items, tabName).length : total;
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

    // Called by lookup-filters.js after a filter toggle: re-renders the active
    // tab's grid against the new filter set. Defers the rebuild one frame so
    // the click's visual feedback — active class on the dashboard row, pie/line
    // dimming via :has(), filter badge appearing/disappearing — paints
    // immediately. The grid (rebuild 50 cards + reflow into columns +
    // equalize) is the slow part (~30–50ms on a sizeable collection); running
    // it inline blocks the browser from painting the cheap visual updates
    // until it finishes. Coalesce rapid toggles so multiple clicks don't queue
    // redundant rerenders against the same final filter state.
    window._lookupApplyFilter = function(tabName) {
        var s = state[tabName];
        if (!s || !s.items) return;
        var rerender = function() {
            applyPage(tabName, 1);
            syncControls(tabName);
            _syncTabCount(tabName, s);
            if (window._layoutMatchGrids) window._layoutMatchGrids();
        };
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
            window._withLookupScroll(function() {
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
            window._withLookupScroll(function() {
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
