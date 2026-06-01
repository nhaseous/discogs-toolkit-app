// Add border-bottom to page-header while navigating away after a search
(function() {
    var form = document.getElementById('lookup-form');
    if (!form) return;
    form.addEventListener('submit', function() {
        var header = document.querySelector('.page-header');
        if (header) header.classList.add('page-header--searching');
    });
})();

// List sub-tab: intercept list index clicks, AJAX-load releases, create sub-tab dynamically
(function() {
    var listsPanel = document.getElementById("lookup-panel-lists");
    if (!listsPanel) return;

    function _closeExistingList() {
        var p = document.getElementById("lookup-panel-list");
        if (p && p.parentNode) p.parentNode.removeChild(p);
        var t = document.querySelector('.lookup-tab[data-tab="list"]');
        if (t && t.parentNode) t.parentNode.removeChild(t);
        var m = document.getElementById("lookup-mosaic-list");
        if (m) {
            m.innerHTML = '';
            m.classList.add("lookup-mosaic--inactive");
            delete m.dataset.populated;
        }
    }

    function createListPanel() {
        var p = document.createElement("div");
        p.id = "lookup-panel-list";
        p.className = "lookup-panel";
        p.style.display = "none";
        p.innerHTML = '<div class="match-grid"></div>';
        var ref = document.getElementById("lookup-panel-lists");
        ref.parentNode.insertBefore(p, ref.nextSibling);
        return p;
    }

    function createListTab(listName) {
        var container = document.querySelector(".lookup-tabs");
        var tab = document.createElement("button");
        tab.className = "lookup-tab";
        tab.type = "button";
        tab.setAttribute("data-tab", "list");
        if (container) container.appendChild(tab);
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
        if (window._markListEntry) window._markListEntry();

        var titleEl = card.querySelector(".match-card-title");
        var listName = titleEl ? titleEl.textContent.trim() : "List";

        // Always close the previously-opened list (tab + panel + mosaic) before
        // opening the new one — keeps state clean and gives the user clear
        // visual feedback that the prior list is gone.
        _closeExistingList();

        var listPanel = createListPanel();
        var listTab = createListTab(listName);
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
                var countText = listName + ": " + count + " release" + (count !== 1 ? "s" : "");

                listTab.disabled = false;
                listTab.textContent = listName + " (" + count + ")";
                listTab.setAttribute("data-count-text", countText);

                Mosaic.populate(document.getElementById("lookup-mosaic-list"), releases, { tag: 'span' });

                var countEl = document.getElementById("lookup-count");
                var countUrl = listTab.getAttribute("data-count-url") || '';
                if (countEl) {
                    if (countUrl) {
                        countEl.innerHTML = '<a href="' + countUrl + '" target="_blank" rel="noopener noreferrer" class="meta-user-link">' + countText + '</a>';
                    } else {
                        countEl.textContent = countText;
                    }
                }

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

// Insights dashboard filter click handling
(function() {
    var collDash = document.getElementById('collection-insights-dash');
    var wantDash = document.getElementById('wantlist-insights-dash');
    var dashes = [collDash, wantDash].filter(Boolean);

    // Wantlist insights are rendered lazily on first tab activation — fetch once,
    // inject right after the collection dashboard, then treat as a normal wantDash.
    var wantlistFetchState = 'idle';  // idle | loading | done
    function _ensureWantlistInsights(onReady) {
        if (wantlistFetchState === 'done') { if (onReady) onReady(); return; }
        if (wantlistFetchState === 'loading') return;
        var dataEl = document.querySelector('.lookup-data[data-tab="wantlist"]');
        if (!dataEl) return;
        var items;
        try { items = JSON.parse(dataEl.textContent); } catch (e) { return; }
        if (!items || !items.length) { wantlistFetchState = 'done'; return; }
        wantlistFetchState = 'loading';
        fetch('/lookup/insights', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: items, kind: 'wantlist' })
        }).then(function(r) { return r.json(); }).then(function(d) {
            if (d && d.html) {
                var anchor = collDash || document.querySelector('.lookup-mosaic-wrap');
                if (anchor && anchor.parentNode) {
                    anchor.insertAdjacentHTML('afterend', d.html);
                    wantDash = document.getElementById('wantlist-insights-dash');
                    if (wantDash && dashes.indexOf(wantDash) === -1) {
                        dashes.push(wantDash);
                        if (typeof _bindDashListeners === 'function') _bindDashListeners(wantDash);
                    }
                }
            }
            wantlistFetchState = 'done';
            if (onReady) onReady();
        }).catch(function() {
            wantlistFetchState = 'idle';  // allow retry on next tab activation
        });
    }

    window._onLookupTabChange = function(tabName) {
        if (tabName === 'wantlist' && wantlistFetchState !== 'done') {
            _ensureWantlistInsights(function() {
                if (window._onLookupTabChange) window._onLookupTabChange(tabName);
            });
        }
        // Only show a dashboard when its matching tab is active — the lists and
        // (user) list subtabs get a clean view with no insights.
        if (collDash) {
            collDash.style.display = (tabName === 'collection') ? '' : 'none';
            collDash.classList.toggle('insights-filters-disabled', tabName !== 'collection');
        }
        if (wantDash) {
            wantDash.style.display = (tabName === 'wantlist') ? '' : 'none';
            wantDash.classList.toggle('insights-filters-disabled', tabName !== 'wantlist');
        }
        if (window._syncLookupFilterBadges) window._syncLookupFilterBadges();
    };

    // Lookup-browse calls this after lazy-injecting a dashboard from /lookup/load-tab.
    // We need to capture the new node in collDash/wantDash and bind hover/click listeners.
    window._registerLookupDash = function(tabName) {
        var dash = null;
        if (tabName === 'collection') {
            collDash = document.getElementById('collection-insights-dash');
            dash = collDash;
        } else if (tabName === 'wantlist') {
            wantDash = document.getElementById('wantlist-insights-dash');
            dash = wantDash;
            // The lazy /lookup/load-tab path already produced wantlist insights —
            // suppress the legacy /lookup/insights POST so we don't double-render.
            wantlistFetchState = 'done';
        }
        if (dash && dashes.indexOf(dash) === -1) {
            dashes.push(dash);
            _bindDashListeners(dash);
        }
        if (dash && window._observeLookupLineGraphs) window._observeLookupLineGraphs(dash);
        // Apply the visibility/active-class state for the current tab now that
        // we've captured the new node.
        var active = document.querySelector('.lookup-tab.active');
        if (active) window._onLookupTabChange(active.getAttribute('data-tab'));
    };

    window._deactivateDashFilter = function(field, value, tabName) {
        var targets;
        if (tabName === 'collection') targets = [collDash];
        else if (tabName === 'wantlist') targets = [wantDash];
        else targets = dashes;
        targets.forEach(function(d) {
            if (!d) return;
            d.querySelectorAll('.insights-filter-row').forEach(function(r) {
                if (r.getAttribute('data-filter-field') === field &&
                    r.getAttribute('data-filter-value') === value) {
                    r.classList.remove('insights-filter-active');
                }
            });
        });
    };

    // Note: we deliberately do NOT early-return when there are no dashboards on
    // initial paint. With list_id-deferred loading, the collection dashboard is
    // injected later by /lookup/load-tab; _registerLookupDash needs the function
    // declarations + line-graph observer set up below.

    var initTab = document.querySelector('.lookup-tab.active');
    if (initTab) window._onLookupTabChange(initTab.getAttribute('data-tab'));

    // Cross-hover: hovering any .insights-filter-row highlights matching peers
    function _clearCrossHover(d) {
        d.querySelectorAll('.insights-filter-hover, .is-pt-hover').forEach(function(r) {
            r.classList.remove('insights-filter-hover', 'is-pt-hover');
        });
    }

    // A line graph dims everything but the focused point(s); the focus state is the
    // presence of a hovered, cross-hovered, or selected point. Recompute it on each
    // hover/select change rather than relying on :has()/<g>:hover.
    function _refreshLineFocus(d) {
        d.querySelectorAll('.insights-line-graph-svg').forEach(function(svg) {
            var focused = svg.querySelector(
                '.insights-line-pt.is-pt-hover,' +
                '.insights-line-pt.insights-filter-hover,' +
                '.insights-line-pt.insights-filter-active');
            svg.classList.toggle('is-pt-focused', !!focused);
        });
    }

    function _bindDashListeners(dash) {
        if (!dash || dash._listenersBound) return;
        dash._listenersBound = true;
        dash.addEventListener('mouseover', function(e) {
            var row = e.target.closest('.insights-filter-row');
            if (!row || row.contains(e.relatedTarget)) return;
            _clearCrossHover(dash);
            var field = row.getAttribute('data-filter-field');
            var value = row.getAttribute('data-filter-value');
            if (!field || value === null) return;
            dash.querySelectorAll('.insights-filter-row').forEach(function(r) {
                if (r !== row &&
                    r.getAttribute('data-filter-field') === field &&
                    r.getAttribute('data-filter-value') === value) {
                    r.classList.add('insights-filter-hover');
                }
            });

            // Hovering an Added History line-graph point marks it as the hovered
            // point (so the graph dims everything else) and scrolls the matching
            // year row to the top of the (often single-row-tall) breakdown table,
            // so the hovered year is the one visible in the scroll window.
            if (row.closest('.insights-line-graph-wrap') && row.classList.contains('insights-line-pt')) {
                row.classList.add('is-pt-hover');
                var scrollEl = dash.querySelector('.insights-added-scroll');
                var tr = scrollEl && scrollEl.querySelector(
                    'tr.insights-filter-row[data-filter-field="' + field +
                    '"][data-filter-value="' + value + '"]');
                if (tr) {
                    var top = scrollEl.scrollTop +
                        (tr.getBoundingClientRect().top - scrollEl.getBoundingClientRect().top);
                    scrollEl.scrollTo({ top: top, behavior: 'smooth' });
                }
            }
            _refreshLineFocus(dash);
        });
        dash.addEventListener('mouseout', function(e) {
            var row = e.target.closest('.insights-filter-row');
            if (!row || row.contains(e.relatedTarget)) return;
            _clearCrossHover(dash);
            _refreshLineFocus(dash);
        });
        _bindDashClick(dash);
    }
    window._bindDashListeners = _bindDashListeners;

    function _bindDashClick(dash) {
        var dashTab = (dash === wantDash) ? 'wantlist' : 'collection';
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

            if (window._toggleLookupFilter) window._toggleLookupFilter(field, value, dashTab);

            if (isActive) {
                row.classList.add('insights-filter-flash');
                row.addEventListener('animationend', function() {
                    row.classList.remove('insights-filter-flash');
                }, { once: true });
            }

            _refreshLineFocus(dash);
        });
    }

    dashes.forEach(_bindDashListeners);

    // Line graph visual scaling.
    // The SVG uses preserveAspectRatio="none" so the line reflows to the available
    // width while text labels and dots stay non-distorted. We pin the SVG height to
    // VH * (13/9) so that:
    //   • y-scale = 13/9 → font-size 9 SVG units renders at exactly 13px CSS
    //     (matching rec-sf-name in the adjacent breakdown table)
    //   • ROW_H 18 SVG units renders at 18 * 13/9 = 26px CSS, matching the table
    //     row height so gridlines align with rows
    // An inverse x-scale transform is applied to text and circle elements to undo
    // the horizontal stretch introduced by preserveAspectRatio="none".
    function _scaleLineGraph(svg) {
        var VW = parseFloat(svg.dataset.vw || '312');
        var VH = parseFloat(svg.dataset.vh || '106');
        var svgW = svg.getBoundingClientRect().width;
        if (!svgW) return;

        // Fixed height: keeps labels at 13px and gridlines at 26px regardless
        // of the graph's container width.
        var fixedH = Math.round(VH * 13 / 9);
        svg.style.height = fixedH + 'px';

        // Undo the horizontal stretch so labels and dots stay non-distorted.
        var xCorr = (fixedH / VH) / (svgW / VW);  // yScale / xScale

        svg.querySelectorAll(':scope > text').forEach(function(el) {
            var x = parseFloat(el.getAttribute('x')) || 0;
            el.setAttribute('transform',
                'translate(' + x + ',0) scale(' + xCorr + ',1) translate(' + (-x) + ',0)');
        });

        svg.querySelectorAll(':scope > .insights-line-pt, :scope > circle.insights-line-dot').forEach(function(el) {
            var c = el.tagName.toLowerCase() === 'circle' ? el : el.querySelector('circle');
            var xref = c ? (parseFloat(c.getAttribute('cx')) || 0) : 0;
            el.setAttribute('transform',
                'translate(' + xref + ',0) scale(' + xCorr + ',1) translate(' + (-xref) + ',0)');
        });
    }

    // Single shared ResizeObserver so lazily-injected dashboards (collection or
    // wantlist) can hook in without spinning up new observers per render.
    var _lineGraphRO = window.ResizeObserver ? new ResizeObserver(function(entries) {
        entries.forEach(function(e) { _scaleLineGraph(e.target); });
    }) : null;
    function _observeLineGraphs(root) {
        if (!_lineGraphRO) return;
        (root || document).querySelectorAll('.insights-line-graph-svg[data-vw]').forEach(function(svg) {
            _lineGraphRO.observe(svg);
        });
    }
    window._observeLookupLineGraphs = _observeLineGraphs;
    _observeLineGraphs();
})();

// Collection folder subtabs: re-clicking the already-active Collection tab
// fetches the user's folder names once (GET /lookup/folders) and adds a subtab
// per folder. The items themselves aren't refetched — each subtab is just the
// already-loaded collection split by each item's folder_id. The subtabs are
// plain DOM, so they persist while switching to other tabs and vanish on a page
// refresh. Wired to the hook in lookup-browse.js's tab click handler.
(function() {
    var collTab = document.querySelector('.lookup-tab[data-tab="collection"]');
    if (!collTab) return;

    var _built = false;  // build (and fetch) at most once per page load

    // Resolve the full collection item list. _lookupHydrateTab returns the
    // already-hydrated items (or triggers/awaits the cached hydration fetch —
    // no extra Discogs call); fall back to the inline subset if unavailable.
    function _collectionItems() {
        if (window._lookupHydrateTab) return Promise.resolve(window._lookupHydrateTab('collection'));
        var el = document.querySelector('.lookup-data[data-tab="collection"]');
        var items = [];
        try { items = el ? JSON.parse(el.textContent) : []; } catch (e) { items = []; }
        return Promise.resolve(items);
    }

    function _buildFolderTabs(folders, items) {
        var tabsContainer = document.querySelector('.lookup-tabs');
        var collPanel = document.getElementById('lookup-panel-collection');
        var mosaicWrap = document.querySelector('.lookup-mosaic-wrap');
        if (!tabsContainer || !collPanel) return;
        var afterTab = collTab, afterPanel = collPanel;
        folders.forEach(function(f) {
            var fItems = items.filter(function(it) { return it.folder_id === f.id; });
            var count = fItems.length;

            var tab = document.createElement('button');
            tab.type = 'button';
            tab.className = 'lookup-tab lookup-tab--folder';
            tab.setAttribute('data-tab', 'folder-' + f.id);
            tab.setAttribute('data-folder-tab', '1');
            tab.textContent = f.name + ' (' + count + ')';
            tab.setAttribute('data-count-text', f.name + ': ' + count + ' item' + (count !== 1 ? 's' : ''));
            afterTab.insertAdjacentElement('afterend', tab);
            afterTab = tab;

            var panel = document.createElement('div');
            panel.id = 'lookup-panel-folder-' + f.id;
            panel.className = 'lookup-panel';
            panel.style.display = 'none';
            panel.innerHTML = '<div class="match-grid"></div>';
            afterPanel.insertAdjacentElement('afterend', panel);
            afterPanel = panel;

            // Give the folder its own thumbnail mosaic in the shared wrap,
            // alongside the collection/wantlist/list mosaics. Starts empty +
            // inactive; switchMosaics() lazily populates it from the folder's
            // registered state.items on first open and animates the swap
            // (collection -> folder, or folder -> folder) like the other tabs.
            if (mosaicWrap) {
                var mosaic = document.createElement('div');
                mosaic.id = 'lookup-mosaic-folder-' + f.id;
                mosaic.className = 'lookup-mosaic mosaic lookup-mosaic--inactive';
                mosaic.setAttribute('data-mosaic-tab', 'folder-' + f.id);
                mosaicWrap.appendChild(mosaic);
            }

            // Registers pagination state + renders the first page into the
            // (hidden) grid; doTabSwitch re-lays it out when the tab opens.
            if (window._registerAndApplyTab) window._registerAndApplyTab('folder-' + f.id, fItems, false);
        });
    }

    window._onCollectionReclick = function() {
        if (_built) return;
        _built = true;
        var qs = new URLSearchParams(window.location.search);
        var username = qs.get('username') || '';
        if (!username) { _built = false; return; }

        fetch('/lookup/folders?username=' + encodeURIComponent(username), {
            headers: { 'Accept': 'application/json' }
        })
            .then(function(r) { return r.ok ? r.json() : { folders: [] }; })
            .then(function(data) {
                // Skip folder 0 ("All") — the Collection tab already covers it.
                var named = ((data && data.folders) || []).filter(function(f) { return f && f.id !== 0; });
                if (!named.length) return;  // non-owner / no custom folders: degrade gracefully
                return _collectionItems().then(function(items) { _buildFolderTabs(named, items || []); });
            })
            .catch(function() { _built = false; });  // allow a retry on the next re-click
    };
})();
