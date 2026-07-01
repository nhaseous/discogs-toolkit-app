(function() {
    var badgeCount = document.querySelector(".badge-count");
    if (!badgeCount) return;

    function getActiveContainer() {
        var sorted = document.getElementById('pc-list-sorted');
        if (sorted && sorted.style.display !== 'none') return sorted;
        var unsorted = document.getElementById('pc-list-unsorted');
        if (unsorted) return unsorted;
        return document;
    }

    function updateBadgeCounts() {
        var container = getActiveContainer();
        var containerSelector = container.id ? "#" + container.id : null;
        ToolkitUtils.updateBadgeCounts(containerSelector, ".badge-count");
    }

    // Exposed so reprice.js (loaded after this file) can refresh counts
    // and query the active list container without re-implementing them.
    window._pcUpdateBadgeCounts = updateBadgeCounts;
    window._pcGetActiveContainer = getActiveContainer;

    function ordinal(n) {
        return ToolkitUtils.ordinal(n);
    }

    var seller = (window.PC_PENDING && window.PC_PENDING.seller) ||
                 new URLSearchParams(window.location.search).get("seller") || "";

    // --- Watchlist (own store only) ---
    var watchedIds = new Set();
    (function() {
        var user = window.TOOLKIT_CONFIG ? window.TOOLKIT_CONFIG.session_user : null;
        if (!user || !seller || user.toLowerCase() !== seller.toLowerCase()) return;

        var watchBadge = badgeCount.querySelector(".inv-count-badge[data-filter='watch']");
        if (!watchBadge) return;

        document.body.classList.add("is-own-store");

        var saveTimer = null;

        function getWatchedIds() {
            var ids = [];
            document.querySelectorAll(".result-card").forEach(function(card) {
                if ((card.getAttribute("data-badges") || "").split(" ").indexOf("watch") !== -1) {
                    var id = card.id.replace("card-", "");
                    if (ids.indexOf(id) === -1) ids.push(id);
                }
            });
            return ids;
        }

        function scheduleSave() {
            clearTimeout(saveTimer);
            saveTimer = setTimeout(function() {
                ToolkitAPI.postWatchlist(seller, getWatchedIds());
            }, 600);
        }

        function makeEyeBtn() {
            var btn = document.createElement("button");
            btn.className = "card-watch-toggle";
            btn.title = "Add to watchlist";
            btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
            return btn;
        }

        function makeWatchBadge() {
            var span = document.createElement("span");
            span.className = "card-watch-badge-inline";
            span.innerHTML = 'WATCH<span class="card-watch-x">&times;</span>';
            return span;
        }

        function setCardWatched(card, watched) {
            var numSpan = card.querySelector(".card-number > span");
            if (!numSpan) return;
            var existing = numSpan.querySelector(".card-watch-toggle, .card-watch-badge-inline");
            if (existing) existing.remove();
            var el = watched ? makeWatchBadge() : makeEyeBtn();
            el.addEventListener("click", function(e) {
                e.stopPropagation();
                e.preventDefault();
                toggleWatch(card);
            });
            numSpan.appendChild(el);
        }

        function toggleWatch(card) {
            var badges = (card.getAttribute("data-badges") || "").split(" ").filter(Boolean);
            var idx = badges.indexOf("watch");
            var willWatch = idx === -1;
            if (willWatch) badges.push("watch");
            else badges.splice(idx, 1);
            card.setAttribute("data-badges", badges.join(" "));
            setCardWatched(card, willWatch);
            // Sync to same release in the other container
            document.querySelectorAll('[id="' + card.id + '"]').forEach(function(c) {
                if (c === card) return;
                var cb = (c.getAttribute("data-badges") || "").split(" ").filter(Boolean);
                var ci = cb.indexOf("watch");
                if (willWatch && ci === -1) cb.push("watch");
                else if (!willWatch && ci !== -1) cb.splice(ci, 1);
                c.setAttribute("data-badges", cb.join(" "));
                setCardWatched(c, willWatch);
            });
            updateBadgeCounts();
            scheduleSave();
        }

        // Apply the watch eye-button / badge to a single card based on its
        // current state plus the loaded watchlist set. Called per card as
        // they stream in, and on clones built for the sorted view.
        window._pcInitWatchForCard = function(card) {
            var id = card.id.replace("card-", "");
            if (watchedIds.has(id)) {
                var b = (card.getAttribute("data-badges") || "").split(" ").filter(Boolean);
                if (b.indexOf("watch") === -1) {
                    b.push("watch");
                    card.setAttribute("data-badges", b.join(" "));
                }
            }
            var watched = (card.getAttribute("data-badges") || "").split(" ").indexOf("watch") !== -1;
            setCardWatched(card, watched);
        };

        // Load watchlist from Firestore, then apply to any cards already present.
        ToolkitAPI.getWatchlist(seller)
            .then(function(data) {
                (data.watchlist || []).forEach(function(id) { watchedIds.add(String(id)); });
                document.querySelectorAll(".result-card").forEach(function(card) {
                    window._pcInitWatchForCard(card);
                });
                updateBadgeCounts();
            });
    })();

    // --- Sorted-by-place view (built client-side from streamed results) ---
    var loaded = [];   // { index, place, el } — el is the unsorted card node
    window._pcRegisterLoaded = function(item) { loaded.push(item); };

    // When the page is restored from a static snapshot (e.g. a saved
    // .webarchive) the streaming loader never runs, so the in-memory `loaded`
    // list is empty even though the cards are present in the DOM. Rebuild it
    // from the unsorted list so toggling "sort by place" still works offline.
    function ensureLoadedFromDom() {
        if (loaded.length) return;
        var src = document.getElementById('pc-list-unsorted');
        if (!src) return;
        src.querySelectorAll('.result-card').forEach(function(el, i) {
            var idx = parseInt(el.getAttribute('data-index'), 10);
            if (isNaN(idx)) idx = i;
            var place = parseInt(el.getAttribute('data-place'), 10);
            if (isNaN(place)) {
                // Fallback for snapshots saved before data-place existed: the
                // place renders as "(n)" in the card number row.
                var row = el.querySelector('.card-number-right');
                var m = row && row.textContent.match(/\((\d+)\)/);
                place = m ? parseInt(m[1], 10) : 0;
            }
            loaded.push({ index: idx, place: place, el: el });
        });
    }

    function buildSortedView() {
        var sortedDiv = document.getElementById('pc-list-sorted');
        if (!sortedDiv) return;
        ensureLoadedFromDom();

        var groups = [];
        for (var i = 0; i < 10; i++) groups.push([]);
        loaded.forEach(function(item) {
            if (!item.place || item.place <= 0) return;
            var gi = item.place < 10 ? item.place - 1 : 9;
            groups[gi].push(item);
        });

        var activeIdx = [];
        groups.forEach(function(g, i) { if (g.length) activeIdx.push(i); });

        sortedDiv.innerHTML = "";
        var wrap = document.createElement("div");
        wrap.className = "sorted-results";

        var summary = document.createElement("div");
        summary.className = "place-summary";
        var title = document.createElement("div");
        title.className = "place-summary-title";
        title.textContent = "Place Summary";
        summary.appendChild(title);
        activeIdx.forEach(function(gi) {
            var n = gi + 1;
            var a = document.createElement("a");
            a.href = "#place-" + n;
            a.className = "place-summary-link";
            a.textContent = ordinal(n);
            summary.appendChild(a);
            summary.appendChild(document.createTextNode(": " + groups[gi].length));
            summary.appendChild(document.createElement("br"));
        });
        wrap.appendChild(summary);

        var running = 0;
        activeIdx.forEach(function(gi, ai) {
            var n = gi + 1;
            var count = groups[gi].length;
            var hdr = document.createElement("div");
            hdr.className = "sort-group-header";
            hdr.id = "place-" + n;
            var label = document.createElement("span");
            label.textContent = ordinal(n) + " Place — " + count + " listing" + (count !== 1 ? "s" : "");
            hdr.appendChild(label);
            var nav = document.createElement("span");
            nav.className = "place-nav-buttons";
            if (ai > 0) {
                var prev = document.createElement("a");
                prev.href = "#place-" + (activeIdx[ai - 1] + 1);
                prev.className = "place-nav-btn";
                prev.innerHTML = "&#8592; Prev";
                nav.appendChild(prev);
            }
            if (ai < activeIdx.length - 1) {
                var next = document.createElement("a");
                next.href = "#place-" + (activeIdx[ai + 1] + 1);
                next.className = "place-nav-btn";
                next.innerHTML = "Next &#8594;";
                nav.appendChild(next);
            }
            hdr.appendChild(nav);
            wrap.appendChild(hdr);

            groups[gi].slice().sort(function(a, b) { return a.index - b.index; }).forEach(function(item) {
                running++;
                var clone = item.el.cloneNode(true);
                clone.classList.remove("pc-card-enter");
                clone.classList.remove("pc-card-in");
                var numSpan = clone.querySelector(".card-number > span");
                if (numSpan && numSpan.firstChild && numSpan.firstChild.nodeType === 3) {
                    numSpan.firstChild.nodeValue = "#" + running;
                }
                wrap.appendChild(clone);
                if (window._pcInitWatchForCard) window._pcInitWatchForCard(clone);
            });
        });

        sortedDiv.appendChild(wrap);
    }
    window._pcBuildSortedView = buildSortedView;

    // --- Sort toggle ---
    (function() {
        var sortToggle = document.getElementById('sort');
        var unsortedDiv = document.getElementById('pc-list-unsorted');
        var sortedDiv = document.getElementById('pc-list-sorted');
        if (!sortToggle || !unsortedDiv || !sortedDiv) return;
        sortToggle.addEventListener('change', function() {
            if (window._pcIsRepriceActive && window._pcIsRepriceActive()) { this.checked = !this.checked; return; }
            var showSorted = this.checked;
            if (showSorted) buildSortedView();
            unsortedDiv.style.display = showSorted ? 'none' : '';
            sortedDiv.style.display = showSorted ? '' : 'none';
            updateBadgeCounts();
        });
    })();

    // --- Smooth-scroll handlers for place nav + mosaic (delegated, so they
    //     work for the dynamically built sorted view) ---
    document.addEventListener("click", function(e) {
        var link = e.target.closest(".place-nav-btn, .place-summary-link");
        if (link) {
            e.preventDefault();
            var el = document.getElementById(link.getAttribute("href").slice(1));
            if (!el) return;
            el.style.position = "static";
            var top = el.getBoundingClientRect().top + window.scrollY;
            el.style.position = "";
            window.scrollTo({ top: top, behavior: "smooth" });
            return;
        }
        var item = e.target.closest("a.mosaic-item");
        if (!item) return;
        e.preventDefault();
        var target = document.getElementById(item.getAttribute("href").slice(1));
        if (!target) return;
        var top2 = target.getBoundingClientRect().top + window.scrollY;
        var hdr = document.querySelector(".sort-group-header");
        var hdrOffset = hdr ? hdr.getBoundingClientRect().height : 0;
        var mosaicEl = document.getElementById("results-mosaic");
        var mosaicOffset = (mosaicEl && getComputedStyle(mosaicEl).display !== "none")
            ? mosaicEl.getBoundingClientRect().height + 26 : 10;
        window.scrollTo({ top: top2 - hdrOffset - mosaicOffset, behavior: "smooth" });
    });
})();

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
    // Re-apply active filters to cards that stream in after a filter is set.
    window._pcReapplyFilters = function() { if (active.size) filter(); };
})();

(function() {
    var mosaic = document.getElementById("results-mosaic");
    if (!mosaic) return;
    var container = mosaic.closest(".content");
    var contentMain = document.getElementById("content-main");
    var invCount = mosaic.nextElementSibling;

    Mosaic.attachSticky(mosaic, {
        container: container,
        leftAnchorEl: contentMain,
        returnEl: invCount,
        clipEl: contentMain,
        onStickyCreated: function(sticky) {
            if (!invCount) return null;
            var observers = [];
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
                observers.push(mo);
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
                    observers.push(moBtn);
                });
                var moRC = new MutationObserver(function() {
                    cloneRC.style.cssText = origRC.style.cssText;
                });
                moRC.observe(origRC, { attributes: true, attributeFilter: ["style"] });
                observers.push(moRC);
                var origStatus = origRC.querySelector(".reprice-status");
                var cloneStatus = cloneRC.querySelector(".reprice-status");
                if (origStatus && cloneStatus) {
                    var moSt = new MutationObserver(function() {
                        cloneStatus.style.cssText = origStatus.style.cssText;
                        cloneStatus.textContent = origStatus.textContent;
                    });
                    moSt.observe(origStatus, { attributes: true, attributeFilter: ["style"], childList: true, characterData: true, subtree: true });
                    observers.push(moSt);
                }
            }
            sticky.appendChild(cloned);
            return observers;
        },
    });
})();

// --- Progressive loader: stream cards in as each scrape batch returns ---
(function() {
    var cfg = window.PC_PENDING;
    if (!cfg || !cfg.seller) return;
    var dataEl = document.getElementById("pc-pending-data");
    var releases = [];
    try { releases = JSON.parse(dataEl.textContent || "[]"); } catch (e) {}
    if (!releases.length) return;

    // If cards are already in the DOM, this page was restored from a static
    // snapshot (e.g. a saved .webarchive) rather than a fresh search. Re-running
    // the streaming loader would re-scrape (failing offline) and, on finish,
    // rebuild the sorted "Place Summary" view from the empty in-memory `loaded`
    // array — wiping the saved results. Leave the snapshot untouched.
    if (document.querySelector("#pc-list-unsorted .result-card, #pc-list-sorted .result-card")) return;

    var unsorted = document.getElementById("pc-list-unsorted");
    var sortedDiv = document.getElementById("pc-list-sorted");
    var mosaic = document.getElementById("results-mosaic");
    var spinner = document.getElementById("spinner");
    var statusEl = document.getElementById("pc-load-status");
    var timeWrap = document.getElementById("pc-load-time");
    var timeVal = document.getElementById("pc-load-time-val");

    var seller = cfg.seller;
    var total = releases.length;
    var startT = Date.now();
    var cfBlocked = false;

    // One batch in flight at a time: combined with the server's 5 scrape workers
    // this reproduces the original single-session, ~5-concurrent request pattern,
    // which Cloudflare tolerates far better than many parallel cold scrapers.
    var BATCH = 10, MAX_INFLIGHT = 1, BATCH_TIMEOUT_MS = 60000;
    var batches = [];
    for (var i = 0; i < releases.length; i += BATCH) batches.push(releases.slice(i, i + BATCH));
    var bi = 0, inflight = 0, batchesDone = 0;

    // Releases that fail (Cloudflare block, timeout, network) are collected and
    // retried in additional passes so a transient block doesn't leave permanent
    // gaps in the inventory.
    var releaseByIndex = {};
    releases.forEach(function(r) { releaseByIndex[r.index] = r; });
    var failed = [];
    var addedCount = 0;
    var retryPass = 0, MAX_RETRY_PASSES = 3, RETRY_DELAY_MS = 1500;

    if (spinner) spinner.style.display = "block";

    function insertOrdered(container, el, idx) {
        var kids = container.children;
        for (var j = 0; j < kids.length; j++) {
            var ci = parseInt(kids[j].getAttribute("data-index") || "-1", 10);
            if (ci > idx) { container.insertBefore(el, kids[j]); return; }
        }
        container.appendChild(el);
    }

    function addResult(res) {
        if (res.error) return;
        var tmp = document.createElement("div");
        tmp.innerHTML = (res.card_html || "").trim();
        var card = tmp.firstElementChild;
        if (!card) return;
        // Guard against a release arriving twice across retry passes.
        if (document.getElementById(card.id)) return;
        addedCount++;
        card.setAttribute("data-index", res.index);
        card.classList.add("pc-card-enter");
        insertOrdered(unsorted, card, res.index);
        requestAnimationFrame(function() {
            requestAnimationFrame(function() { card.classList.add("pc-card-in"); });
        });

        if (res.thumb && mosaic) {
            var a = Mosaic.buildItem({
                thumb: res.thumb,
                anchorId: card.id,
                index: res.index,
                reveal: true,
            });
            insertOrdered(mosaic, a, res.index);
        }

        if (window._pcInitWatchForCard) window._pcInitWatchForCard(card);
        if (window._pcRegisterLoaded) window._pcRegisterLoaded({ index: res.index, place: res.place, el: card });
    }

    function updateProgress() {
        if (!statusEl) return;
        var label = "Loading " + Math.min(addedCount, total) + " of " + total + "…";
        if (retryPass > 0 && failed.length) label = "Retrying " + failed.length + " of " + total + "…";
        statusEl.textContent = label;
    }

    function finish() {
        if (spinner) spinner.style.display = "none";
        // The badge-count row only becomes meaningful once every release has
        // been scraped, so it stays hidden until loading completes.
        var badgeRow = document.querySelector(".badge-count");
        if (badgeRow) badgeRow.style.display = "";
        if (window._pcBuildSortedView && sortedDiv) window._pcBuildSortedView();
        if (window._pcUpdateBadgeCounts) window._pcUpdateBadgeCounts();
        if (window._pcReapplyFilters) window._pcReapplyFilters();

        var missing = total - addedCount;
        if (missing > 0 && statusEl) {
            statusEl.textContent = missing + " of " + total + " could not be loaded (Cloudflare). Re-run the search to retry.";
        } else if (statusEl) {
            statusEl.style.display = "none";
            if (timeWrap) {
                if (timeVal) timeVal.textContent = ((Date.now() - startT) / 1000).toFixed(2);
                timeWrap.style.display = "";
            }
        }
    }

    function markFailed(release) { if (release) failed.push(release); }

    function handleBatch(d) {
        if (d && d.cf_blocked) cfBlocked = true;
        ((d && d.results) || []).forEach(function(res) {
            if (res.error) markFailed(releaseByIndex[res.index]);
            else addResult(res);
        });
        updateProgress();
        if (window._pcUpdateBadgeCounts) window._pcUpdateBadgeCounts();
        if (window._pcReapplyFilters) window._pcReapplyFilters();
        if (sortedDiv && sortedDiv.style.display !== "none" && window._pcBuildSortedView) {
            window._pcBuildSortedView();
        }
    }

    function runBatch(batch) {
        // AbortController guarantees the request settles even if the server
        // hangs on a stalled scrape, so the loader can never freeze.
        var ctrl = (typeof AbortController !== "undefined") ? new AbortController() : null;
        var timer = setTimeout(function() { if (ctrl) try { ctrl.abort(); } catch (e) {} }, BATCH_TIMEOUT_MS);
        
        ToolkitAPI.scrapeBatch(seller, batch, ctrl ? ctrl.signal : undefined)
        .then(function(d) { clearTimeout(timer); handleBatch(d); })
        .catch(function() { clearTimeout(timer); batch.forEach(markFailed); updateProgress(); })
        .then(function() {
            inflight--;
            batchesDone++;
            if (bi < batches.length) pump();
            else if (batchesDone === batches.length) maybeRetryOrFinish();
        });
    }

    function maybeRetryOrFinish() {
        if (failed.length && retryPass < MAX_RETRY_PASSES) {
            retryPass++;
            var retryReleases = failed;
            failed = [];
            for (var i = 0; i < retryReleases.length; i += BATCH) {
                batches.push(retryReleases.slice(i, i + BATCH));
            }
            updateProgress();
            // Brief pause so Cloudflare clearance settles before retrying.
            setTimeout(pump, RETRY_DELAY_MS);
        } else {
            finish();
        }
    }

    function pump() {
        while (inflight < MAX_INFLIGHT && bi < batches.length) {
            inflight++;
            runBatch(batches[bi++]);
        }
    }

    updateProgress();
    pump();
})();
