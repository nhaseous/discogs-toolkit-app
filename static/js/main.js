var _lookupActiveFilters = {};
function _lookupGetFilteredItems(items) {
    var fields = Object.keys(_lookupActiveFilters);
    if (!fields.length) return items;
    return items.filter(function(item) {
        for (var fi = 0; fi < fields.length; fi++) {
            var field = fields[fi];
            var vals = _lookupActiveFilters[field];
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

document.querySelectorAll(".sidebar a").forEach(function(link) {
    link.addEventListener("click", function(e) {
        if (this.pathname === window.location.pathname) {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: "smooth" });
            history.replaceState(null, "", window.location.pathname + window.location.search);
        }
    });
});

(function() {
    var active = new Set();
    var pills = document.querySelectorAll(".inv-count-badge[data-filter]");
    if (!pills.length) return;
    pills.forEach(function(pill) {
        pill.addEventListener("click", function() {
            var f = this.getAttribute("data-filter");
            if (active.has(f)) {
                active.delete(f);
                this.classList.remove("filter-active");
                if (f === "low") {
                    active.delete("lowest");
                    var lb = document.querySelector(".inv-count-badge[data-filter='lowest']");
                    if (lb) lb.classList.remove("filter-active");
                }
            } else {
                active.add(f);
                this.classList.add("filter-active");
                if (f === "lowest") {
                    active.add("low");
                    var lowb = document.querySelector(".inv-count-badge[data-filter='low']");
                    if (lowb) lowb.classList.add("filter-active");
                }
                if (f === "recent") {
                    active.delete("old");
                    var oldb = document.querySelector(".inv-count-badge[data-filter='old']");
                    if (oldb) oldb.classList.remove("filter-active");
                }
                if (f === "old") {
                    active.delete("recent");
                    var recentb = document.querySelector(".inv-count-badge[data-filter='recent']");
                    if (recentb) recentb.classList.remove("filter-active");
                }
            }
            filter();
        });
    });
    function filter() {
        document.querySelectorAll(".result-card").forEach(function(card) {
            if (!active.size) { card.style.display = ""; return; }
            var cb = (card.getAttribute("data-badges") || "").split(" ");
            var show = true;
            active.forEach(function(f) { if (cb.indexOf(f) === -1) show = false; });
            card.style.display = show ? "" : "none";
        });
        document.querySelectorAll(".sort-group-header").forEach(function(hdr) {
            if (!active.size) { hdr.style.display = ""; return; }
            var sib = hdr.nextElementSibling;
            var vis = false;
            while (sib && !sib.classList.contains("sort-group-header")) {
                if (sib.classList.contains("result-card") && sib.style.display !== "none") { vis = true; break; }
                sib = sib.nextElementSibling;
            }
            hdr.style.display = vis ? "" : "none";
        });
    }
})();

(function() {
    var mosaic = document.getElementById("results-mosaic");
    if (!mosaic) return;
    var container = mosaic.closest(".content");
    var sticky = null;
    var syncObservers = [];
    function reposition() {
        if (!sticky) return;
        sticky.style.left = document.getElementById("content-main").getBoundingClientRect().right + 48 + "px";
    }
    function activate() {
        if (sticky) return;
        sticky = document.createElement("div");
        sticky.id = "sticky-mosaic";
        mosaic.querySelectorAll(".mosaic-item").forEach(function(item) {
            sticky.appendChild(item.cloneNode(true));
        });
        var invCount = mosaic.nextElementSibling;
        if (invCount) {
            var cloned = invCount.cloneNode(true);
            cloned.querySelectorAll(".inv-count-badge[data-filter]").forEach(function(cb) {
                cb.addEventListener("click", function(e) {
                    e.stopPropagation();
                    var orig = invCount.querySelector(".inv-count-badge[data-filter='" + this.getAttribute("data-filter") + "']");
                    if (orig) orig.click();
                });
            });
            invCount.querySelectorAll(".inv-count-badge[data-filter]").forEach(function(ob) {
                var mo = new MutationObserver(function() {
                    var cb = cloned.querySelector(".inv-count-badge[data-filter='" + ob.getAttribute("data-filter") + "']");
                    if (cb) cb.classList.toggle("filter-active", ob.classList.contains("filter-active"));
                });
                mo.observe(ob, { attributes: true, attributeFilter: ["class"] });
                syncObservers.push(mo);
            });
            var origRC = invCount.querySelector(".reprice-controls");
            var cloneRC = cloned.querySelector(".reprice-controls");
            if (origRC && cloneRC) {
                var origBtns = origRC.querySelectorAll("button");
                var cloneBtns = cloneRC.querySelectorAll("button");
                cloneBtns.forEach(function(cloneBtn, idx) {
                    var origBtn = origBtns[idx];
                    if (!origBtn) return;
                    cloneBtn.addEventListener("click", function(e) {
                        e.stopPropagation();
                        origBtn.click();
                    });
                    var moBtn = new MutationObserver(function() {
                        cloneBtn.style.cssText = origBtn.style.cssText;
                        cloneBtn.className = origBtn.className;
                        if (cloneBtn.textContent !== origBtn.textContent) cloneBtn.textContent = origBtn.textContent;
                    });
                    moBtn.observe(origBtn, { attributes: true, attributeFilter: ["style", "class"], childList: true, characterData: true, subtree: true });
                    syncObservers.push(moBtn);
                });
                var moRC = new MutationObserver(function() {
                    cloneRC.style.cssText = origRC.style.cssText;
                });
                moRC.observe(origRC, { attributes: true, attributeFilter: ["style"] });
                syncObservers.push(moRC);
                var origStatus = origRC.querySelector(".reprice-status");
                var cloneStatus = cloneRC.querySelector(".reprice-status");
                if (origStatus && cloneStatus) {
                    var moSt = new MutationObserver(function() {
                        cloneStatus.style.cssText = origStatus.style.cssText;
                        cloneStatus.textContent = origStatus.textContent;
                    });
                    moSt.observe(origStatus, { attributes: true, attributeFilter: ["style"], childList: true, characterData: true, subtree: true });
                    syncObservers.push(moSt);
                }
            }
            sticky.appendChild(cloned);
        }
        document.body.appendChild(sticky);
        reposition();
        window.addEventListener("resize", reposition);
        container.classList.add("sticky-mosaic-active");
        sticky.style.transform = "translateY(-100%)";
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                if (!sticky) return;
                sticky.style.transition = "transform 0.35s cubic-bezier(0.4,0,0.2,1)";
                sticky.style.transform = "translateY(0)";
            });
        });
    }
    var MOSAIC_EASE = "transform 0.35s cubic-bezier(0.4,0,0.2,1), opacity 0.28s ease";
    function slideInMosaic() {
        var w = mosaic.offsetWidth;
        var clip = document.getElementById("content-main");
        if (clip) clip.style.overflow = "hidden";
        mosaic.style.transition = "none";
        mosaic.style.transform = "translateX(-" + w + "px)";
        mosaic.style.opacity = "0";
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                mosaic.style.transition = MOSAIC_EASE;
                mosaic.style.transform = "translateX(0)";
                mosaic.style.opacity = "1";
                mosaic.addEventListener("transitionend", function cleanup(e) {
                    if (e.propertyName !== "transform") return;
                    mosaic.removeEventListener("transitionend", cleanup);
                    mosaic.style.transition = "";
                    mosaic.style.transform = "";
                    mosaic.style.opacity = "";
                    if (clip) clip.style.overflow = "";
                });
            });
        });
    }
    function revealMosaic() {
        container.classList.remove("sticky-mosaic-active");
        slideInMosaic();
    }
    function deactivate() {
        if (!sticky) return;
        syncObservers.forEach(function(mo) { mo.disconnect(); });
        syncObservers = [];
        window.removeEventListener("resize", reposition);
        var el = sticky;
        sticky = null;
        el.style.transition = "transform 0.35s cubic-bezier(0.4,0,0.2,1)";
        el.style.transform = "translateY(-100%)";
        el.addEventListener("transitionend", function() { el.remove(); revealMosaic(); }, { once: true });
    }
    new IntersectionObserver(function(entries) {
        if (!entries[0].isIntersecting && entries[0].boundingClientRect.top < 0) { activate(); }
    }).observe(mosaic);
    var invCount = mosaic.nextElementSibling;
    if (invCount) {
        new IntersectionObserver(function(entries) {
            if (!entries[0].isIntersecting) return;
            if (sticky) { deactivate(); return; }
            if (!container.classList.contains("sticky-mosaic-active")) return;
            revealMosaic();
        }).observe(invCount);
    }
    slideInMosaic();
})();

(function() {
    var tip = document.getElementById("badge-tooltip");
    if (!tip) return;
    document.querySelectorAll(".inv-count-badge[data-tooltip]").forEach(function(badge) {
        badge.addEventListener("mouseenter", function(e) {
            var s = window.getComputedStyle(this);
            tip.textContent = this.getAttribute("data-tooltip");
            tip.style.background = s.backgroundColor;
            tip.style.color = s.color;
            tip.style.left = e.clientX + "px";
            tip.style.top = e.clientY + "px";
            tip.style.display = "block";
        });
        badge.addEventListener("mousemove", function(e) {
            tip.style.left = e.clientX + "px";
            tip.style.top = e.clientY + "px";
        });
        badge.addEventListener("mouseleave", function() {
            tip.style.display = "none";
        });
    });
})();

(function() {
    function attachFormAnim(formId) {
        var form = document.getElementById(formId);
        if (!form) return;
        form.addEventListener("submit", function(e) {
            e.preventDefault();
            form.nextElementSibling.style.display = "block";
            var header = document.querySelector(".page-header");
            if (header) {
                var formRect = form.getBoundingClientRect();
                var gap = parseInt(window.getComputedStyle(form).marginBottom) || 22;
                var targetTop = 30;
                var delta = targetTop - formRect.top;
                if (delta < 0) {
                    var headerShift = (targetTop + formRect.height + gap) - header.getBoundingClientRect().top;
                    var ease = "transform 0.4s cubic-bezier(0.4,0,0.2,1)";
                    form.style.transition = ease;
                    form.style.transform = "translateY(" + delta + "px)";
                    header.style.transition = ease;
                    header.style.transform = "translateY(" + headerShift + "px)";
                    form.addEventListener("transitionend", function() { form.submit(); }, { once: true });
                    return;
                }
            }
            requestAnimationFrame(function() { requestAnimationFrame(function() { form.submit(); }); });
        });
    }
    attachFormAnim("pc-form");
    attachFormAnim("matcher-form");
    attachFormAnim("lookup-form");
})();

(function() {
    function layoutMatchGrid(grid) {
        if (!grid.offsetParent) return;
        var allCards = Array.from(grid.querySelectorAll(".match-card"));
        if (!allCards.length) return;
        var gap = 14, minWidth = 158;
        var numCols = Math.max(1, Math.floor((grid.offsetWidth + gap) / (minWidth + gap)));
        var existing = Array.from(grid.children);
        if (existing.length === numCols && existing.every(function(c) { return c.classList.contains("match-column"); })) return;
        grid.innerHTML = "";
        var cols = [];
        for (var i = 0; i < numCols; i++) {
            var col = document.createElement("div");
            col.className = "match-column";
            grid.appendChild(col);
            cols.push(col);
        }
        allCards.forEach(function(c, i) { cols[i % numCols].appendChild(c); });
    }
    window._layoutMatchGrids = function() {
        document.querySelectorAll(".match-grid").forEach(layoutMatchGrid);
    };
    window._layoutMatchGrids();
    var _lgTimer;
    window.addEventListener("resize", function() {
        clearTimeout(_lgTimer);
        _lgTimer = setTimeout(window._layoutMatchGrids, 100);
    });
})();

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
            var sourceItems = (tabName === 'collection') ? _lookupGetFilteredItems(s.items) : s.items;
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
    function _syncCollectionTabCount(cs) {
        var isFiltered = Object.keys(_lookupActiveFilters).length > 0;
        var total = cs.items.length;
        var filtered = isFiltered ? _lookupGetFilteredItems(cs.items).length : total;
        var collTab = document.querySelector('.lookup-tab[data-tab="collection"]');
        if (!collTab) return;
        // Lock width on first filter so the button doesn't resize
        if (!collTab._lockedWidth) {
            collTab.style.minWidth = collTab.offsetWidth + 'px';
            collTab._lockedWidth = true;
        }
        collTab.textContent = 'Collection (' + filtered + ')';
        var countText = filtered + ' item' + (filtered !== 1 ? 's' : '');
        collTab.setAttribute('data-count-text', countText);
        var countEl = document.getElementById('lookup-count');
        if (countEl && collTab.classList.contains('active')) {
            countEl.textContent = countText;
        }
        // Release width lock when filters are cleared
        if (!isFiltered) {
            collTab.style.minWidth = '';
            collTab._lockedWidth = false;
        }
    }
    var _exclusiveFilterFields = window._exclusiveFilterFields = {};
    var _filterBadgesEl = document.getElementById('lookup-filter-badges');
    function _syncFilterBadges() {
        if (!_filterBadgesEl) return;
        _filterBadgesEl.innerHTML = '';
        Object.keys(_lookupActiveFilters).forEach(function(field) {
            _lookupActiveFilters[field].forEach(function(value) {
                var badge = document.createElement('span');
                badge.className = 'lookup-filter-badge';
                badge.innerHTML = _esc(value) + '<span class="lookup-filter-badge-x">&times;</span>';
                badge.addEventListener('click', function() {
                    if (window._deactivateDashFilter) window._deactivateDashFilter(field, value);
                    window._toggleLookupFilter(field, value);
                });
                _filterBadgesEl.appendChild(badge);
            });
        });
    }
    window._toggleLookupFilter = function(field, value) {
        if (!_lookupActiveFilters[field]) _lookupActiveFilters[field] = new Set();
        var fset = _lookupActiveFilters[field];
        if (fset.has(value)) {
            fset.delete(value);
            if (!fset.size) delete _lookupActiveFilters[field];
        } else {
            if (_exclusiveFilterFields[field]) fset.clear();
            fset.add(value);
        }
        _syncFilterBadges();
        var cs = state['collection'];
        if (cs && cs.items) {
            applyPage('collection', 1);
            syncControls('collection');
            _syncCollectionTabCount(cs);
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

(function() {
    if (window.location.pathname === "/") {
        sessionStorage.removeItem("art-tab");
        return;
    }
    var art = document.querySelector(".sidebar-art");
    if (!art) return;
    var activeLink = document.querySelector(".sidebar a.active");
    var currentTab = activeLink ? activeLink.getAttribute("href") : "";
    var prevTab = sessionStorage.getItem("art-tab");
    var artAnimating = prevTab !== currentTab;
    if (artAnimating) {
        var sidebar = document.querySelector(".sidebar");
        sidebar.style.overflow = "hidden";
        art.style.transform = "translateY(150px)";
        art.style.opacity = "0";
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                art.style.transition = "transform 0.55s cubic-bezier(0.4,0,0.2,1), opacity 0.4s ease";
                art.style.transform = "";
                art.style.opacity = "";
                art.addEventListener("transitionend", function cleanup(e) {
                    if (e.propertyName !== "transform") return;
                    art.style.transition = "";
                    sidebar.style.overflow = "";
                    art.removeEventListener("transitionend", cleanup);
                });
            });
        });
        sessionStorage.setItem("art-tab", currentTab);
    }
    var platter = document.querySelector(".sidebar-platter");
    if (!platter) return;

    platter.setAttribute("title", "Export page as PDF");
    platter.setAttribute("role", "button");
    platter.setAttribute("aria-label", "Export page as PDF");
    platter.addEventListener("click", function() {
        var path = window.location.pathname;
        var qs = new URLSearchParams(window.location.search);
        var pageNames = {
            "/": "Home",
            "/pricechecker": "Price Checker",
            "/matcher": "Matcher",
            "/lookup": "Lookup",
            "/records": "Records"
        };
        var parts = ["Discogs Toolkit", pageNames[path] || path.replace(/^\//, "") || "Page"];
        if (path === "/pricechecker" && qs.get("seller")) parts.push(qs.get("seller"));
        else if (path === "/matcher" && (qs.get("collection") || qs.get("wantlist"))) {
            parts.push((qs.get("collection") || "?") + " + " + (qs.get("wantlist") || "?"));
        }
        else if (path === "/lookup" && qs.get("username")) {
            var u = qs.get("username");
            if (qs.get("list_id")) u += " list " + qs.get("list_id");
            parts.push(u);
        }
        var originalTitle = document.title;
        document.title = parts.join(" - ");
        var restore = function() {
            document.title = originalTitle;
            window.removeEventListener("afterprint", restore);
        };
        window.addEventListener("afterprint", restore);
        window.print();
    });

    platter.style.transform = "translateY(150px)";
    platter.style.opacity = "0";
    setTimeout(function() {
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                platter.style.transition = "transform 0.5s cubic-bezier(0.4,0,0.2,1), opacity 0.4s ease";
                platter.style.transform = "translateY(0)";
                platter.style.opacity = "1";
                platter.addEventListener("transitionend", function onDone(e) {
                    if (e.propertyName !== "transform") return;
                    platter.style.transition = "";
                    platter.style.transform = "";
                    platter.style.opacity = "";
                    platter.classList.add("spinning");
                    platter.removeEventListener("transitionend", onDone);
                });
            });
        });
    }, artAnimating ? 600 : 200);
})();

// List sub-tab: intercept list index clicks, AJAX-load releases, create sub-tab dynamically
(function() {
    var listsPanel = document.getElementById("lookup-panel-lists");
    if (!listsPanel) return;

    function getOrCreateListPanel() {
        var p = document.getElementById("lookup-panel-list");
        if (p) {
            var g = p.querySelector(".match-grid");
            if (g) g.innerHTML = '';
            var d = p.querySelector(".lookup-data");
            if (d) d.remove();
            var e = p.querySelector(".match-empty");
            if (e) e.remove();
            return p;
        }
        p = document.createElement("div");
        p.id = "lookup-panel-list";
        p.className = "lookup-panel";
        p.style.display = "none";
        p.innerHTML = '<div class="match-grid"></div>';
        var ref = document.getElementById("lookup-panel-lists");
        ref.parentNode.insertBefore(p, ref.nextSibling);
        return p;
    }

    function getOrCreateListTab(listName) {
        var container = document.querySelector(".lookup-tabs");
        var tab = document.querySelector('.lookup-tab[data-tab="list"]');
        if (!tab) {
            tab = document.createElement("button");
            tab.className = "lookup-tab";
            tab.type = "button";
            tab.setAttribute("data-tab", "list");
            if (container) container.appendChild(tab);
        }
        tab.textContent = listName + "…";
        tab.setAttribute("data-count-text", "");
        return tab;
    }

    listsPanel.addEventListener("click", function(e) {
        var card = e.target.closest(".match-card");
        if (!card) return;
        var href = card.getAttribute("href") || "";
        var qi = href.indexOf("?");
        var listId = new URLSearchParams(qi !== -1 ? href.slice(qi + 1) : "").get("list_id");
        if (!listId) return;
        e.preventDefault();

        var titleEl = card.querySelector(".match-card-title");
        var listName = titleEl ? titleEl.textContent.trim() : "List";

        var listPanel = getOrCreateListPanel();
        var listTab = getOrCreateListTab(listName);
        listTab.disabled = true;

        if (window._switchToTab) window._switchToTab("list");

        var params = new URLSearchParams(window.location.search);
        params.set("list_id", listId);
        history.pushState(null, "", window.location.pathname + "?" + params.toString());

        fetch("/lookup/list?list_id=" + encodeURIComponent(listId))
            .then(function(r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(function(data) {
                var releases = data.releases || [];
                var count = releases.length;
                var countText = count + " release" + (count !== 1 ? "s" : "");

                listTab.disabled = false;
                listTab.textContent = listName + " (" + count + ")";
                listTab.setAttribute("data-count-text", countText);

                var mosaic = document.getElementById("lookup-mosaic-list");
                if (mosaic) {
                    mosaic.innerHTML = '';
                    releases.forEach(function(m) {
                        if (!m.thumb) return;
                        var span = document.createElement("span");
                        span.className = "mosaic-item";
                        var img = document.createElement("img");
                        img.src = m.thumb;
                        img.className = "mosaic-thumb";
                        img.alt = "";
                        img.loading = "lazy";
                        span.appendChild(img);
                        mosaic.appendChild(span);
                    });
                }

                var countEl = document.getElementById("lookup-count");
                if (countEl) countEl.textContent = countText;

                if (!releases.length) {
                    var emptyEl = document.createElement("p");
                    emptyEl.className = "match-empty";
                    emptyEl.textContent = "This list is empty.";
                    listPanel.appendChild(emptyEl);
                }

                if (window._registerAndApplyTab) window._registerAndApplyTab("list", releases, false);
            })
            .catch(function() {
                listTab.disabled = false;
                listTab.textContent = listName + " (error)";
                var emptyEl = document.createElement("p");
                emptyEl.className = "match-empty";
                emptyEl.textContent = "Failed to load this list. Please try again.";
                listPanel.appendChild(emptyEl);
            });
    });
})();

// Match-card hover sequencing: queue next card open until closing animation finishes
(function() {
    if (!document.querySelector(".match-grid")) return;
    var activeCard = null;
    var pendingCard = null;
    var closeTimer = null;
    var DURATION = 290; // matches 0.28s CSS transition + small buffer

    function activate(card) {
        clearTimeout(closeTimer);
        closeTimer = null;
        pendingCard = null;
        if (activeCard && activeCard !== card) activeCard.classList.remove("match-card--active");
        activeCard = card;
        card.classList.add("match-card--active");
    }

    function deactivate(card) {
        card.classList.remove("match-card--active");
        if (activeCard === card) activeCard = null;
        clearTimeout(closeTimer);
        closeTimer = setTimeout(function() {
            closeTimer = null;
            if (pendingCard) { var next = pendingCard; pendingCard = null; activate(next); }
        }, DURATION);
    }

    document.addEventListener("mouseover", function(e) {
        var card = e.target.closest(".match-card:not(.match-card--back)");
        if (!card) return;
        var grid = card.closest(".match-grid");
        if (grid && grid.classList.contains("match-grid--expanded")) return;
        if (card === activeCard) return;
        if (closeTimer) {
            pendingCard = card;
        } else if (activeCard) {
            deactivate(activeCard);
            pendingCard = card;
        } else {
            activate(card);
        }
    });

    document.addEventListener("mouseout", function(e) {
        var card = e.target.closest(".match-card:not(.match-card--back)");
        if (!card || card.contains(e.relatedTarget)) return;
        var grid = card.closest(".match-grid");
        if (grid && grid.classList.contains("match-grid--expanded")) return;
        if (pendingCard === card) { pendingCard = null; return; }
        if (activeCard === card) deactivate(card);
    });

    window._resetMatchCardHover = function() {
        clearTimeout(closeTimer);
        closeTimer = null;
        pendingCard = null;
        if (activeCard) { activeCard.classList.remove("match-card--active"); activeCard = null; }
    };
})();

// Insights dashboard filter click handling
(function() {
    var collDash = document.getElementById('collection-insights-dash');
    var wantDash = document.getElementById('wantlist-insights-dash');
    var dashes = [collDash, wantDash].filter(Boolean);

    window._onLookupTabChange = function(tabName) {
        if (collDash) {
            collDash.style.display = (tabName === 'wantlist') ? 'none' : '';
            collDash.classList.toggle('insights-filters-disabled', tabName !== 'collection');
        }
        if (wantDash) {
            wantDash.style.display = (tabName === 'wantlist') ? '' : 'none';
            wantDash.classList.add('insights-filters-disabled');
        }
    };

    window._deactivateDashFilter = function(field, value) {
        dashes.forEach(function(d) {
            d.querySelectorAll('.insights-filter-row').forEach(function(r) {
                if (r.getAttribute('data-filter-field') === field &&
                    r.getAttribute('data-filter-value') === value) {
                    r.classList.remove('insights-filter-active');
                }
            });
        });
    };

    if (!dashes.length) return;

    var initTab = document.querySelector('.lookup-tab.active');
    if (initTab) window._onLookupTabChange(initTab.getAttribute('data-tab'));

    dashes.forEach(function(dash) {
        dash.addEventListener('click', function(e) {
            var expandBtn = e.target.closest('.breakdown-expand');
            if (expandBtn) {
                var panel = expandBtn.closest('.breakdown-expandable');
                if (!panel) return;
                var scroll = panel.querySelector('.rec-breakdown-scroll');
                if (!scroll) return;

                if (panel.classList.contains('is-expanded')) {
                    var finish = function() {
                        panel.classList.remove('is-expanded');
                        scroll.style.maxHeight = '';
                        expandBtn.textContent = '+';
                        expandBtn.setAttribute('title', 'Show all');
                    };
                    if (scroll.scrollTop <= 0) {
                        finish();
                    } else {
                        scroll.scrollTo({ top: 0, behavior: 'smooth' });
                        var start = Date.now();
                        (function tick() {
                            if (scroll.scrollTop <= 1 || Date.now() - start > 600) finish();
                            else requestAnimationFrame(tick);
                        })();
                    }
                } else {
                    var h = scroll.clientHeight;
                    if (h > 0) scroll.style.maxHeight = h + 'px';
                    panel.classList.add('is-expanded');
                    expandBtn.textContent = '−';
                    expandBtn.setAttribute('title', 'Show less');
                }
                return;
            }

            if (dash.classList.contains('insights-filters-disabled')) return;
            var row = e.target.closest('.insights-filter-row');
            if (!row) return;
            var field = row.getAttribute('data-filter-field');
            var value = row.getAttribute('data-filter-value');
            if (!field || value === null) return;

            var isActive = row.classList.toggle('insights-filter-active');

            if (isActive && _exclusiveFilterFields && _exclusiveFilterFields[field]) {
                dash.querySelectorAll('.insights-filter-row[data-filter-field="' + field + '"]').forEach(function(r) {
                    if (r !== row) r.classList.remove('insights-filter-active');
                });
            }

            dash.querySelectorAll('.insights-filter-row').forEach(function(r) {
                if (r !== row &&
                    r.getAttribute('data-filter-field') === field &&
                    r.getAttribute('data-filter-value') === value) {
                    r.classList.toggle('insights-filter-active', isActive);
                }
            });

            if (window._toggleLookupFilter) window._toggleLookupFilter(field, value);

            if (isActive) {
                row.classList.add('insights-filter-flash');
                row.addEventListener('animationend', function() {
                    row.classList.remove('insights-filter-flash');
                }, { once: true });
            }
        });
    });
})();

// External link handling for pywebview (MacOS App)
(function() {
    function getExternalUrl(el) {
        if (!el) return null;
        var href = el.getAttribute('href') || el.dataset.href;
        if (!href) return null;
        
        // Check if it's a relative URL or points to the same host
        var a = document.createElement('a');
        a.href = href;
        if (a.hostname && a.hostname !== window.location.hostname && a.hostname !== 'localhost') {
            return a.href;
        }
        return null;
    }

    function openExternal(url) {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.open_external) {
            window.pywebview.api.open_external(url);
            return true;
        }
        return false;
    }

    document.addEventListener('click', function(e) {
        var el = e.target.closest('a, [data-href]');
        if (!el) return;

        var url = getExternalUrl(el);
        if (url && openExternal(url)) {
            e.preventDefault();
            e.stopPropagation();
        }
    }, true);

    // Intercept window.open
    var originalOpen = window.open;
    window.open = function(url, target, features) {
        if (url) {
            var a = document.createElement('a');
            a.href = url;
            if (a.hostname && a.hostname !== window.location.hostname && a.hostname !== 'localhost') {
                if (openExternal(a.href)) {
                    return null;
                }
            }
        }
        return originalOpen(url, target, features);
    };
})();
