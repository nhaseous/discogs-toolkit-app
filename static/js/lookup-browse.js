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
    var tabsRow = document.querySelector(".lookup-tabs-row");
    var contentMain = document.getElementById("content-main");
    var mosaicWrap = document.querySelector(".lookup-mosaic-wrap");
    var currentY = window.pageYOffset;

    if (contentMain) {
        // Guard total page height to prevent scrollbar jumping.
        contentMain.style.minHeight = (currentY + window.innerHeight) + "px";
    }
    
    if (action) action();

    if (tabsRow) {
        // Measure target position in the final layout state.
        var oldPos = tabsRow.style.position;
        tabsRow.style.position = "static";
        
        // Remove any temporary height guards from switchMosaics to measure the true final offset.
        // We do NOT restore this, so the viewport target and the actual elements stay aligned.
        if (mosaicWrap) mosaicWrap.style.minHeight = "";
        
        var targetY = 0;
        var curr = tabsRow;
        while (curr && curr !== document.body) {
            targetY += curr.offsetTop;
            curr = curr.offsetParent;
        }
        
        tabsRow.style.position = oldPos;
        window.scrollTo({ top: targetY, behavior: "smooth" });
    }

    setTimeout(function() {
        if (contentMain) contentMain.style.minHeight = "";
    }, 600);
}

(function() {
    var tabsContainer = document.querySelector(".lookup-tabs");
    if (!tabsContainer || !tabsContainer.querySelector(".lookup-tab")) return;
    var EASE = "transform 0.35s cubic-bezier(0.4,0,0.2,1), opacity 0.28s ease";
    function switchMosaics(target) {
        var all = Array.from(document.querySelectorAll(".lookup-mosaic"));
        var incoming = document.getElementById("lookup-mosaic-" + target);
        var outgoing = all.find(function(m) { return m !== incoming && !m.classList.contains("lookup-mosaic--inactive"); });

        var wrap = document.querySelector(".lookup-mosaic-wrap");
        if (!wrap) return;
        var w = wrap.offsetWidth;

        if (outgoing) {
            // Set min-height guard only if we have an incoming mosaic to show.
            // For the Lists tab (no mosaic), we collapse immediately to prevent ghost space.
            if (incoming) wrap.style.minHeight = outgoing.offsetHeight + "px";
            else wrap.style.minHeight = "";

            outgoing.classList.add("lookup-mosaic--inactive");
            outgoing.style.visibility = "visible";
            outgoing.style.transition = EASE;
            outgoing.style.transform = "translateX(-" + w + "px)";
            outgoing.style.opacity = "0";
            outgoing.addEventListener("transitionend", function cleanup(e) {
                if (e.propertyName !== "transform") return;
                outgoing.removeEventListener("transitionend", cleanup);
                outgoing.style.visibility = "";
                outgoing.style.transition = "";
                outgoing.style.transform = "";
                outgoing.style.opacity = "";
                if (!incoming) wrap.style.minHeight = "";
            }, { once: true });
        }

        if (incoming) {
            incoming.classList.remove("lookup-mosaic--inactive");
            incoming.style.transition = "none";
            incoming.style.transform = "translateX(-" + w + "px)";
            incoming.style.opacity = "0";
            requestAnimationFrame(function() {
                requestAnimationFrame(function() {
                    incoming.style.transition = EASE;
                    incoming.style.transform = "translateX(0)";
                    incoming.style.opacity = "1";
                    incoming.addEventListener("transitionend", function done(e) {
                        if (e.propertyName !== "transform") return;
                        incoming.removeEventListener("transitionend", done);
                        incoming.style.transition = "";
                        incoming.style.transform = "";
                        incoming.style.opacity = "";
                        wrap.style.minHeight = "";
                    }, { once: true });
                });
            });
        } else if (!outgoing) {
            wrap.style.minHeight = "";
        }
    }
    var countEl = document.getElementById("lookup-count");
    function doTabSwitch(target) {
        var countText = '';
        document.querySelectorAll(".lookup-tab").forEach(function(t) {
            var isTarget = t.getAttribute("data-tab") === target;
            t.classList.toggle("active", isTarget);
            if (isTarget) countText = t.getAttribute("data-count-text") || '';
        });
        document.querySelectorAll(".lookup-panel").forEach(function(panel) {
            panel.style.display = panel.id === "lookup-panel-" + target ? "" : "none";
        });
        switchMosaics(target);
        if (countEl && countText) countEl.textContent = countText;
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
    if (countEl && initTab) countEl.textContent = initTab.getAttribute("data-count-text") || '';
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
        var body = '<div class="match-card-title">' + _esc(m.title) + '</div>'
            + '<div class="match-card-artist">' + _esc(Array.isArray(m.artist) ? m.artist.join(' / ') : (m.artist || '')) + '</div>'
            + (m.format && m.format.length ? '<div class="match-card-format">' + _esc(m.format.join(' / ')) + '</div>' : '')
            + (m.format_descriptions ? '<div class="match-card-format-desc">' + _esc(m.format_descriptions) + '</div>' : '')
            + (m.format_text ? '<div class="match-card-format-text">' + _esc(m.format_text) + '</div>' : '')
            + (m.for_sale && m.for_sale_url ? '<div class="match-card-forsale" data-href="' + _esc(m.for_sale_url) + '" onclick="event.stopPropagation();event.preventDefault();window.open(this.dataset.href,\'_blank\',\'noopener,noreferrer\')">' + _esc(m.for_sale) + '</div>' : '')
            + (m.comment ? '<div class="match-card-comment">' + _esc(m.comment) + '</div>' : '')
            + (showStats && m.stats ? '<div class="match-card-stats">' + _esc(m.stats) + '</div>' : '');
        return '<a href="' + _esc(m.url || '#') + '" class="match-card" target="_blank" rel="noopener noreferrer">'
            + '<div class="match-card-art">' + art + '</div>'
            + '<div class="match-card-body">' + body + '</div>'
            + '</a>';
    }

    var state = {};
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
        if (dataEl) {
            items = JSON.parse(dataEl.textContent);
            showStats = dataEl.getAttribute("data-show-stats") === "1";
        } else {
            cards = grid ? Array.from(grid.querySelectorAll(".match-card:not(.match-card--back)")) : [];
        }
        var count = items ? items.length : (cards ? cards.length : 0);
        var total = Math.max(1, Math.ceil(count / PAGE_SIZE));
        state[name] = { page: 1, total: total, items: items, cards: cards, showStats: showStats, backCard: backCard, ready: false };
    });
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
        if (s && s.items) {
            applyPage(tabName, 1);
            syncControls(tabName);
            _syncTabCount(tabName, s);
            if (window._layoutMatchGrids) window._layoutMatchGrids();
        }
    };
    window._applyTabPage = function(tabName) {
        var s = state[tabName];
        if (!s) return;
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
    pagTabs.forEach(function(tab) {
        applyPage(tab.getAttribute("data-tab"), 1);
    });
    var initTab = document.querySelector(".lookup-tab.active");
    if (initTab) {
        var initName = initTab.getAttribute("data-tab");
        syncControls(initName);
        if (window._layoutMatchGrids) window._layoutMatchGrids();
    }
    function getActiveTab() {
        var a = document.querySelector(".lookup-tab.active");
        return a ? a.getAttribute("data-tab") : null;
    }
    if (prevBtn) prevBtn.addEventListener("click", function() {
        var name = getActiveTab();
        var s = state[name];
        if (s && s.page > 1) {
            _withLookupScroll(function() {
                applyPage(name, s.page - 1);
                syncControls(name);
                if (window._layoutMatchGrids) window._layoutMatchGrids();
            });
        }
    });
    if (nextBtn) nextBtn.addEventListener("click", function() {
        var name = getActiveTab();
        var s = state[name];
        if (s && s.page < s.total) {
            _withLookupScroll(function() {
                applyPage(name, s.page + 1);
                syncControls(name);
                if (window._layoutMatchGrids) window._layoutMatchGrids();
            });
        }
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
    });
})();
