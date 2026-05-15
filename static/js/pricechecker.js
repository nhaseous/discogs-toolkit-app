(function() {
    var badgeCount = document.querySelector(".badge-count");
    if (!badgeCount) return;

    // Hoisted so both watchlist and reprice blocks can read these flags
    var repriceMode = false, reviewMode = false;

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
            if (repriceMode || reviewMode) { this.checked = !this.checked; return; }
            var showSorted = this.checked;
            unsortedDiv.style.display = showSorted ? 'none' : '';
            sortedDiv.style.display = showSorted ? '' : 'none';
            updateBadgeCounts();
        });
    })();

    // --- Reprice ---
    var overpricedBadge = badgeCount.querySelector(".inv-count-badge[data-filter='overpriced']");
    if (!overpricedBadge) return;

    var pillsSpan = badgeCount.querySelector("span");
    var repriceControls = document.createElement("div");
    repriceControls.className = "reprice-controls";
    repriceControls.style.display = "none";
    var repriceBtn = document.createElement("button");
    repriceBtn.className = "reprice-btn";
    repriceBtn.textContent = "REPRICE";
    var addAllBtn = document.createElement("button");
    addAllBtn.className = "reprice-action-btn";
    addAllBtn.textContent = "ADD ALL";
    addAllBtn.style.display = "none";
    var reviewBtn = document.createElement("button");
    reviewBtn.className = "reprice-action-btn";
    reviewBtn.textContent = "REVIEW";
    reviewBtn.style.display = "none";
    var submitBtn = document.createElement("button");
    submitBtn.className = "reprice-action-btn reprice-submit-btn";
    submitBtn.textContent = "SUBMIT";
    submitBtn.style.display = "none";
    var confirmBtn = document.createElement("button");
    confirmBtn.className = "reprice-action-btn reprice-confirm-btn";
    confirmBtn.textContent = "CONFIRM";
    confirmBtn.style.display = "none";
    var spreadWrap = document.createElement("span");
    spreadWrap.className = "reprice-spread-wrap";
    spreadWrap.style.display = "none";
    var spreadPre = document.createElement("span");
    spreadPre.className = "reprice-spread-label";
    spreadPre.textContent = "SPREAD";
    var spreadInput = document.createElement("input");
    spreadInput.type = "number";
    spreadInput.className = "reprice-spread-input";
    spreadInput.value = "10";
    spreadInput.min = "0.1";
    spreadInput.step = "0.5";
    var spreadPct = document.createElement("span");
    spreadPct.className = "reprice-spread-pct";
    spreadPct.textContent = "%";
    spreadWrap.appendChild(spreadPre);
    spreadWrap.appendChild(spreadInput);
    spreadWrap.appendChild(spreadPct);
    var statusEl = document.createElement("span");
    statusEl.className = "reprice-status";
    statusEl.style.display = "none";
    repriceControls.appendChild(repriceBtn);
    repriceControls.appendChild(addAllBtn);
    repriceControls.appendChild(reviewBtn);
    repriceControls.appendChild(spreadWrap);
    repriceControls.appendChild(submitBtn);
    repriceControls.appendChild(confirmBtn);
    repriceControls.appendChild(statusEl);
    badgeCount.appendChild(repriceControls);
    var selectedCards = new Set();
    var hiddenByReview = new Set();
    var addAllState = false;
    var overlay = null;
    function getSpread() {
        var v = parseFloat(spreadInput.value);
        return (!isNaN(v) && v > 0) ? v : 10;
    }
    spreadInput.addEventListener("input", function() {
        selectedCards.forEach(function(card) {
            var rd = [];
            try { rd = JSON.parse(card.getAttribute("data-reprice") || "[]"); } catch(e) {}
            var entryMap = {};
            rd.forEach(function(e) { entryMap[e.id] = e; });
            card.querySelectorAll("input.reprice-price-input").forEach(function(inp) {
                var entry = entryMap[inp.getAttribute("data-lid")];
                if (!entry) return;
                inp.value = computeNewPrice(entry).toFixed(2);
                inp.dispatchEvent(new Event("input"));
            });
        });
    });
    function updateOverlay() {
        var needs = (repriceMode && selectedCards.size > 0) || reviewMode;
        if (needs && !overlay) {
            overlay = document.createElement("div");
            overlay.id = "reprice-overlay";
            document.body.appendChild(overlay);
        } else if (!needs && overlay) {
            overlay.remove(); overlay = null;
        }
        document.querySelectorAll(".result-card").forEach(function(card) {
            card.classList.toggle("reprice-review-visible", card.classList.contains("reprice-selected"));
        });
        if (needs) { badgeCount.classList.add("reprice-review-bar"); }
        else { badgeCount.classList.remove("reprice-review-bar"); }
    }
    new MutationObserver(function() {
        if (overpricedBadge.classList.contains("filter-active")) {
            repriceControls.style.display = "";
        } else {
            repriceControls.style.display = "none";
            if (repriceMode) exitRepriceMode();
        }
    }).observe(overpricedBadge, {attributes: true, attributeFilter: ["class"]});
    repriceBtn.addEventListener("click", function() {
        if (!repriceMode) enterRepriceMode(); else exitRepriceMode();
    });
    function _repriceAuthNotice(msg) {
        statusEl.textContent = msg;
        statusEl.style.display = "";
        repriceControls.style.display = "";
    }
    function enterRepriceMode() {
        var seller = new URLSearchParams(window.location.search).get("seller") || "";
        var user = window.TOOLKIT_CONFIG ? window.TOOLKIT_CONFIG.session_user : null;
        if (!user) {
            _repriceAuthNotice("Log in to use REPRICE");
            return;
        }
        if (seller && user.toLowerCase() !== seller.toLowerCase()) {
            _repriceAuthNotice("You can only reprice your own listings (signed in as " + user + ")");
            return;
        }
        repriceMode = true;
        repriceBtn.classList.add("active");
        pillsSpan.style.display = "none";
        addAllBtn.style.display = "";
        reviewBtn.style.display = "";
        spreadWrap.style.display = "";
        statusEl.style.display = "none";
        confirmBtn.style.display = "none";
        document.querySelectorAll(".result-card").forEach(function(card) {
            card.classList.add("reprice-selectable");
            card.addEventListener("click", onCardClick);
        });
    }
    function exitRepriceMode() {
        if (reviewMode) exitReviewMode();
        repriceMode = false;
        repriceBtn.classList.remove("active");
        pillsSpan.style.display = "";
        addAllBtn.style.display = "none";
        reviewBtn.style.display = "none";
        spreadWrap.style.display = "none";
        submitBtn.style.display = "none";
        confirmBtn.style.display = "none";
        statusEl.style.display = "none";
        addAllBtn.textContent = "ADD ALL";
        addAllState = false;
        selectedCards.forEach(function(card) { deselectCard(card); });
        selectedCards.clear();
        document.querySelectorAll(".result-card.reprice-selectable").forEach(function(card) {
            card.classList.remove("reprice-selectable");
            card.removeEventListener("click", onCardClick);
        });
        updateOverlay();
    }
    function onCardClick(e) {
        if (reviewMode) return;
        if (e.target.tagName === "INPUT") return;
        if (e.target.tagName === "A" || e.target.closest("a")) return;
        var card = this;
        if (card.classList.contains("reprice-selected")) {
            deselectCard(card); selectedCards.delete(card);
        } else {
            selectCard(card); selectedCards.add(card);
        }
        updateOverlay();
    }
    function computeNewPrice(entry) {
        var spread = getSpread();
        var pct = (entry.seller_price - entry.cheapest_price) / entry.cheapest_price * 100;
        var np = pct > spread ? entry.seller_price * (1 - spread / 100) : entry.cheapest_price - 0.5;
        return Math.round(np * 100) / 100;
    }
    function selectCard(card) {
        card.classList.add("reprice-selected");
        var rd = [];
        try { rd = JSON.parse(card.getAttribute("data-reprice") || "[]"); } catch(e) {}
        if (!rd.length) return;
        var entryMap = {};
        rd.forEach(function(e) { entryMap[e.id] = e; });
        card.querySelectorAll("mark").forEach(function(mark) {
            var a = mark.querySelector("a");
            if (!a) return;
            var href = a.getAttribute("href") || "";
            var mt = href.match(/\/sell\/item\/(\d+)/);
            if (!mt) return;
            var entry = entryMap[mt[1]];
            if (!entry) return;
            var newP = computeNewPrice(entry);
            mark.setAttribute("data-orig-html", mark.innerHTML);

            var del = document.createElement("del");
            del.className = "reprice-old";
            del.textContent = "$" + entry.seller_price.toFixed(2);

            var arrow = document.createElement("span");
            arrow.className = "reprice-arrow";
            arrow.textContent = " → ";

            var input = document.createElement("input");
            input.type = "number";
            input.className = "reprice-price-input";
            input.value = newP.toFixed(2);
            input.min = "0.01";
            input.step = "0.01";
            input.setAttribute("data-lid", mt[1]);
            input.setAttribute("data-seller-price", entry.seller_price.toFixed(2));

            var link = document.createElement("a");
            link.href = href;
            link.target = "_blank";
            link.className = "reprice-new";
            link.textContent = " " + entry.condition + " (You)";

            mark.innerHTML = "";
            mark.appendChild(del);
            mark.appendChild(arrow);
            mark.appendChild(document.createTextNode("$"));
            mark.appendChild(input);
            mark.appendChild(link);

            var pctSpan = document.createElement("span");
            pctSpan.className = "reprice-pct";
            function makePctUpdater(inp, sellerPrice, span) {
                return function() {
                    var val = parseFloat(inp.value);
                    if (isNaN(val) || val <= 0) { span.textContent = ""; return; }
                    var pct = (val - sellerPrice) / sellerPrice * 100;
                    span.textContent = "(" + (pct >= 0 ? "+" : "") + pct.toFixed(0) + "%)";
                };
            }
            var updatePct = makePctUpdater(input, entry.seller_price, pctSpan);
            updatePct();
            input.addEventListener("input", updatePct);
            mark.parentNode.insertBefore(pctSpan, mark.nextSibling);
        });
    }
    function deselectCard(card) {
        card.classList.remove("reprice-selected");
        card.querySelectorAll("mark[data-orig-html]").forEach(function(mark) {
            mark.innerHTML = mark.getAttribute("data-orig-html");
            mark.removeAttribute("data-orig-html");
        });
        card.querySelectorAll(".reprice-pct").forEach(function(el) { el.remove(); });
    }
    addAllBtn.addEventListener("click", function() {
        if (!addAllState) {
            getActiveContainer().querySelectorAll(".result-card").forEach(function(card) {
                if (card.style.display !== "none" && !card.classList.contains("reprice-selected")) {
                    selectCard(card); selectedCards.add(card);
                }
            });
            addAllState = true;
            addAllBtn.textContent = "CLEAR ALL";
        } else {
            selectedCards.forEach(function(card) { deselectCard(card); });
            selectedCards.clear();
            addAllState = false;
            addAllBtn.textContent = "ADD ALL";
        }
        updateOverlay();
    });
    reviewBtn.addEventListener("click", function() {
        if (!reviewMode) enterReviewMode(); else exitReviewMode();
    });
    function enterReviewMode() {
        reviewMode = true;
        reviewBtn.classList.add("active");
        addAllBtn.style.display = "none";
        spreadWrap.style.display = "none";
        submitBtn.style.display = "";
        submitBtn.disabled = false;
        submitBtn.textContent = "SUBMIT";
        confirmBtn.style.display = "none";
        statusEl.style.display = "none";
        document.querySelectorAll(".result-card, .sort-group-header").forEach(function(el) {
            if (!el.classList.contains("reprice-selected") && el.style.display !== "none") {
                el.style.display = "none";
                hiddenByReview.add(el);
            }
        });
        updateOverlay();
    }
    function exitReviewMode() {
        reviewMode = false;
        reviewBtn.classList.remove("active");
        addAllBtn.style.display = "";
        spreadWrap.style.display = "";
        submitBtn.style.display = "none";
        confirmBtn.style.display = "none";
        hiddenByReview.forEach(function(el) { el.style.display = ""; });
        hiddenByReview.clear();
        updateOverlay();
    }
    submitBtn.addEventListener("click", function() {
        if (submitBtn.disabled) return;
        var listings = [];
        selectedCards.forEach(function(card) {
            var rd2 = [];
            try { rd2 = JSON.parse(card.getAttribute("data-reprice") || "[]"); } catch(e) {}
            rd2.forEach(function(entry) {
                var item = {id: entry.id, seller_price: entry.seller_price, cheapest_price: entry.cheapest_price};
                var inp = card.querySelector('input.reprice-price-input[data-lid="' + entry.id + '"]');
                if (inp) {
                    var v = parseFloat(inp.value);
                    if (!isNaN(v) && v > 0) item.custom_price = v;
                }
                listings.push(item);
            });
        });
        if (!listings.length) return;
        submitBtn.disabled = true;
        statusEl.style.display = "none";
        var total = listings.length, done = 0, errCount = 0, errMsgs = [];
        var successCards = new Set();
        function markListingDone(lid) {
            selectedCards.forEach(function(card) {
                card.querySelectorAll("mark").forEach(function(mark) {
                    var lnk = mark.querySelector("a.reprice-new");
                    if (!lnk) return;
                    var mt = (lnk.getAttribute("href") || "").match(/\/sell\/item\/(\d+)/);
                    if (mt && mt[1] === lid) mark.classList.add("mark--done");
                });
            });
        }
        function refreshCards(cardsToRefresh) {
            var seller = new URLSearchParams(window.location.search).get("seller") || "";
            var ri = 0;
            function refreshNext() {
                if (ri >= cardsToRefresh.length) {
                    updateBadgeCounts();
                    return;
                }
                var card = cardsToRefresh[ri++];
                var releaseId = card.id.replace("card-", "");
                var listingIds = [];
                try { listingIds = JSON.parse(card.getAttribute("data-listing-ids") || "[]"); } catch(e) {}
                fetch("/refresh_card", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        seller: seller, release_id: releaseId, listing_ids: listingIds,
                        title: card.getAttribute("data-title") || "",
                        thumbnail: card.getAttribute("data-thumb") || ""
                    })
                })
                .then(function(r) { return r.json(); })
                .then(function(d) {
                    if (d.inner_html) {
                        var numRight = card.querySelector(".card-number-right");
                        if (numRight) numRight.innerHTML = d.price_badges + (d.place_html || "");
                        var cardNum = card.querySelector(".card-number");
                        while (card.lastChild !== cardNum) card.removeChild(card.lastChild);
                        var tmp = document.createElement("div");
                        tmp.innerHTML = d.inner_html;
                        while (tmp.firstChild) card.appendChild(tmp.firstChild);
                        // Preserve watch badge through card refresh
                        var currentBadges = (card.getAttribute("data-badges") || "").split(" ").filter(Boolean);
                        var newBadges = d.data_badges.split(" ").filter(Boolean);
                        if (currentBadges.indexOf("watch") !== -1 && newBadges.indexOf("watch") === -1) {
                            newBadges.push("watch");
                        }
                        card.setAttribute("data-badges", newBadges.join(" "));
                        if (d.reprice_data && d.reprice_data.length) {
                            card.setAttribute("data-reprice", JSON.stringify(d.reprice_data));
                        } else {
                            card.removeAttribute("data-reprice");
                        }
                    }
                    refreshNext();
                })
                .catch(function() { refreshNext(); });
            }
            refreshNext();
        }
        var _seller = new URLSearchParams(window.location.search).get("seller") || "";
        function processNext(i) {
            if (i >= total) {
                submitBtn.textContent = (done - errCount) + " updated" + (errCount ? ", " + errCount + " failed" : "");
                if (errMsgs.length) { statusEl.textContent = errMsgs.join(" | "); statusEl.style.display = ""; }
                var cardsToRefresh = Array.from(successCards);
                confirmBtn.style.display = "";
                confirmBtn.onclick = function() {
                    confirmBtn.style.display = "none";
                    exitRepriceMode();
                    refreshCards(cardsToRefresh);
                };
                return;
            }
            submitBtn.textContent = "Updating " + (i + 1) + " of " + total + "…";
            fetch("/reprice", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({listings: [listings[i]], seller: _seller})
            })
            .then(function(r) {
                return r.json().then(function(data) { return {ok: r.ok, status: r.status, data: data}; });
            })
            .then(function(res) {
                if (!res.ok) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = "SUBMIT";
                    statusEl.textContent = (res.data && res.data.message) ? res.data.message : "Auth error";
                    statusEl.style.display = "";
                    return;
                }
                var data = res.data;
                var result = data.results[0];
                done++;
                if (result && result.status === "success") {
                    markListingDone(String(result.id));
                    selectedCards.forEach(function(card) {
                        var rd2 = [];
                        try { rd2 = JSON.parse(card.getAttribute("data-reprice") || "[]"); } catch(e) {}
                        if (rd2.some(function(e) { return String(e.id) === String(result.id); })) {
                            successCards.add(card);
                        }
                    });
                } else {
                    errCount++;
                    errMsgs.push("#" + (result ? result.id : listings[i].id) + ": " + (result && result.message ? result.message : "error"));
                }
                processNext(i + 1);
            })
            .catch(function() {
                done++; errCount++;
                errMsgs.push("#" + listings[i].id + ": network error");
                processNext(i + 1);
            });
        }
        processNext(0);
    });
})();
