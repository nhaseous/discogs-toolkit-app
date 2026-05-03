(function() {
    var badgeCount = document.querySelector(".badge-count");
    if (!badgeCount) return;
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
    var statusEl = document.createElement("span");
    statusEl.className = "reprice-status";
    statusEl.style.display = "none";
    repriceControls.appendChild(repriceBtn);
    repriceControls.appendChild(addAllBtn);
    repriceControls.appendChild(reviewBtn);
    repriceControls.appendChild(submitBtn);
    repriceControls.appendChild(statusEl);
    badgeCount.appendChild(repriceControls);
    var repriceMode = false, reviewMode = false, addAllState = false, overlay = null;
    var selectedCards = new Set();
    var hiddenByReview = new Set();
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
    function enterRepriceMode() {
        repriceMode = true;
        repriceBtn.classList.add("active");
        pillsSpan.style.display = "none";
        addAllBtn.style.display = "";
        reviewBtn.style.display = "";
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
        submitBtn.style.display = "none";
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
        var pct = (entry.seller_price - entry.cheapest_price) / entry.cheapest_price * 100;
        var np = pct > 10 ? entry.seller_price * 0.9 : entry.cheapest_price - 0.5;
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
            var link = document.createElement("a");
            link.href = href;
            link.target = "_blank";
            link.className = "reprice-new";
            link.textContent = "$" + newP.toFixed(2) + " " + entry.condition + " (You)";
            mark.innerHTML = "";
            mark.appendChild(del);
            mark.appendChild(arrow);
            mark.appendChild(link);
        });
    }
    function deselectCard(card) {
        card.classList.remove("reprice-selected");
        card.querySelectorAll("mark[data-orig-html]").forEach(function(mark) {
            mark.innerHTML = mark.getAttribute("data-orig-html");
            mark.removeAttribute("data-orig-html");
        });
    }
    addAllBtn.addEventListener("click", function() {
        if (!addAllState) {
            document.querySelectorAll(".result-card").forEach(function(card) {
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
        submitBtn.style.display = "";
        submitBtn.disabled = false;
        submitBtn.textContent = "SUBMIT";
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
        submitBtn.style.display = "none";
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
                listings.push({id: entry.id, seller_price: entry.seller_price, cheapest_price: entry.cheapest_price});
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
                if (ri >= cardsToRefresh.length) return;
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
                        card.setAttribute("data-badges", d.data_badges);
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
        function processNext(i) {
            if (i >= total) {
                submitBtn.textContent = (done - errCount) + " updated" + (errCount ? ", " + errCount + " failed" : "");
                if (errMsgs.length) { statusEl.textContent = errMsgs.join(" | "); statusEl.style.display = ""; }
                var cardsToRefresh = Array.from(successCards);
                setTimeout(function() {
                    exitRepriceMode();
                    refreshCards(cardsToRefresh);
                }, 1000);
                return;
            }
            submitBtn.textContent = "Updating " + (i + 1) + " of " + total + "…";
            fetch("/reprice", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({listings: [listings[i]]})
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
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
