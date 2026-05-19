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
        var counts = {
            recent: 0, old: 0, lowest: 0, low: 0, high: 0, highest: 0,
            cheapest: 0, overpriced: 0, watch: 0
        };
        getActiveContainer().querySelectorAll(".result-card").forEach(function(card) {
            var badges = (card.getAttribute("data-badges") || "").split(" ");
            badges.forEach(function(b) { if (counts.hasOwnProperty(b)) counts[b]++; });
        });
        document.querySelectorAll(".badge-count").forEach(function(bc) {
            Object.keys(counts).forEach(function(key) {
                var badge = bc.querySelector(".inv-count-badge[data-filter='" + key + "']");
                if (badge) {
                    var ct = badge.nextElementSibling;
                    if (ct && ct.classList.contains("badge-ct")) {
                        ct.textContent = counts[key];
                    }
                }
            });
        });
    }

    // Exposed so reprice.js (loaded after this file) can refresh counts
    // and query the active list container without re-implementing them.
    window._pcUpdateBadgeCounts = updateBadgeCounts;
    window._pcGetActiveContainer = getActiveContainer;

    // --- Watchlist (own store only) ---
    (function() {
        var seller = new URLSearchParams(window.location.search).get("seller") || "";
        var user = window.TOOLKIT_CONFIG ? window.TOOLKIT_CONFIG.session_user : null;
        if (!user || !seller || user.toLowerCase() !== seller.toLowerCase()) return;

        var watchBadge = badgeCount.querySelector(".inv-count-badge[data-filter='watch']");
        if (!watchBadge) return;

        document.body.classList.add("is-own-store");

        var saveTimer = null;

        function getWatchedIds() {
            var ids = [];
            // Use querySelectorAll to find ALL cards (both sorted and unsorted) to ensure sync
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
                fetch("/watchlist", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({seller: seller, watchlist: getWatchedIds()})
                });
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

        // Insert eye icons into all cards
        document.querySelectorAll(".result-card").forEach(function(card) {
            setCardWatched(card, false);
        });

        // Load watchlist from Firestore and apply watched state to both containers
        fetch("/watchlist?seller=" + encodeURIComponent(seller))
            .then(function(r) { return r.json(); })
            .then(function(data) {
                (data.watchlist || []).forEach(function(id) {
                    document.querySelectorAll('[id="card-' + id + '"]').forEach(function(card) {
                        var badges = (card.getAttribute("data-badges") || "").split(" ").filter(Boolean);
                        if (badges.indexOf("watch") === -1) {
                            badges.push("watch");
                            card.setAttribute("data-badges", badges.join(" "));
                        }
                        setCardWatched(card, true);
                    });
                });
                updateBadgeCounts();
            });
    })();

    // --- Sort toggle ---
    (function() {
        var sortToggle = document.getElementById('sort');
        var unsortedDiv = document.getElementById('pc-list-unsorted');
        var sortedDiv = document.getElementById('pc-list-sorted');
        if (!sortToggle || !unsortedDiv || !sortedDiv) return;
        sortToggle.addEventListener('change', function() {
            if (window._pcIsRepriceActive && window._pcIsRepriceActive()) { this.checked = !this.checked; return; }
            var showSorted = this.checked;
            unsortedDiv.style.display = showSorted ? 'none' : '';
            sortedDiv.style.display = showSorted ? '' : 'none';
            updateBadgeCounts();
        });
    })();
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
