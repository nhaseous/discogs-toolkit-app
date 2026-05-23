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
                var countText = listName + ": " + count + " release" + (count !== 1 ? "s" : "");

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
        if (collDash) {
            collDash.style.display = (tabName === 'wantlist') ? 'none' : '';
            collDash.classList.toggle('insights-filters-disabled', tabName !== 'collection');
        }
        if (wantDash) {
            wantDash.style.display = (tabName === 'wantlist') ? '' : 'none';
            wantDash.classList.toggle('insights-filters-disabled', tabName !== 'wantlist');
        }
        if (window._syncLookupFilterBadges) window._syncLookupFilterBadges();
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

    if (!dashes.length) return;

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
    (function() {
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

        var lineSvgs = document.querySelectorAll('.insights-line-graph-svg[data-vw]');
        if (!lineSvgs.length || !window.ResizeObserver) return;
        var ro = new ResizeObserver(function(entries) {
            entries.forEach(function(e) { _scaleLineGraph(e.target); });
        });
        lineSvgs.forEach(function(svg) { ro.observe(svg); });
    })();
})();
