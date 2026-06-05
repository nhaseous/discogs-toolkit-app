// ==========================================================
// recommend.js — streams recommendation rounds into the page.
//
// The /recommend GET ships only the shell; this driver POSTs to
// /recommend/batch one Gemini round at a time so the first batch of cards (and
// the bio) can paint as soon as a single round resolves, while later rounds are
// appended after the page is already up. State (already-considered suggestions +
// rendered release IDs) is round-tripped so the server stays stateless.
// Loaded after grid.js, which provides window._layoutMatchGrids.
// ==========================================================
(function() {
    var root = document.getElementById("recommend-results");
    if (!root) return;

    var user = root.getAttribute("data-user") || "";
    var newArtists = (root.getAttribute("data-new-artists") || "") === "yes";
    if (!user) return;

    var spinner = document.getElementById("spinner");
    var summary = document.getElementById("recommend-summary");
    var bioEl = document.getElementById("recommend-bio");
    var countLine = document.getElementById("recommend-count-line");
    var countEl = document.getElementById("recommend-count");
    var countLabel = document.getElementById("recommend-count-label");
    var linesEl = document.getElementById("recommend-lines");
    var grid = document.getElementById("recommend-grid");
    var moreEl = document.getElementById("recommend-more");
    var errEl = document.getElementById("recommend-error");
    var metaTime = document.getElementById("recommend-meta-time");

    var considered = [];     // [{artist, album}] round-tripped to avoid repeats
    var seenIds = [];        // resolved release IDs round-tripped to dedupe
    var roundIdx = 0;
    var cardEls = [];        // all rendered card nodes, in insertion order
    var startTime = Date.now();

    function showSpinner(on) { if (spinner) spinner.style.display = on ? "block" : "none"; }
    function showMore(on) { if (moreEl) moreEl.hidden = !on; }

    // On a failure: if cards are already shown, stop quietly and keep them;
    // otherwise replace the spinner with the error message.
    function finishOrError(msg) {
        if (cardEls.length) { showSpinner(false); showMore(false); setMetaTime(); }
        else { showError(msg); }
    }

    function showError(msg) {
        showSpinner(false);
        showMore(false);
        if (summary) summary.hidden = true;
        if (!errEl) return;
        var body = errEl.querySelector(".card-listings");
        if (body) body.textContent = msg;
        errEl.hidden = false;
    }

    function setMetaTime() {
        if (!metaTime) return;
        var secs = ((Date.now() - startTime) / 1000).toFixed(1);
        var now = new Date();
        var t = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
        metaTime.textContent = "Found in " + secs + " seconds  |  " + t;
    }

    function parseCards(html) {
        var tmp = document.createElement("div");
        tmp.innerHTML = html;
        return Array.from(tmp.querySelectorAll(".match-card"));
    }

    function relayoutGrid() {
        // Re-lay out from the flat insertion-ordered list: grid.js reorganizes
        // .match-card nodes into responsive columns, so reset to flat order first
        // (keeping our node references) before asking it to rebuild.
        grid.innerHTML = "";
        cardEls.forEach(function(el) { grid.appendChild(el); });
        if (window._layoutMatchGrids) window._layoutMatchGrids();
    }

    function addBatch(data) {
        var newCards = parseCards(data.cards_html || "");
        newCards.forEach(function(el) { cardEls.push(el); });
        if (newCards.length) relayoutGrid();
        // Text list mirrors the grid; the server renders it (same card data) so we
        // just append its HTML rather than reconstructing it from the cards.
        if (data.lines_html && linesEl) linesEl.insertAdjacentHTML("beforeend", data.lines_html);

        // Bio lives in an always-present span (empty renders nothing), so it just
        // gets filled in — no show/hide needed.
        if (data.bio && bioEl) bioEl.textContent = data.bio;

        // The "N releases" line stays hidden until at least one card exists, so it
        // never flashes "0 releases" mid-search; the card itself (title + intro)
        // is shown from the start to indicate the search is underway.
        if (cardEls.length) {
            if (countLine) countLine.hidden = false;
            if (countEl) countEl.textContent = String(cardEls.length);
            if (countLabel) countLabel.textContent = cardEls.length === 1 ? "release" : "releases";
        }
    }

    function fetchBatch() {
        fetch("/recommend/batch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user: user,
                new_artists: newArtists,
                considered: considered,
                seen_ids: seenIds,
                have: cardEls.length,
                round: roundIdx
            })
        }).then(function(r) {
            return r.json().catch(function() { throw new Error("bad_json"); });
        }).then(function(data) {
            if (data.error) {
                finishOrError(data.message || "Something went wrong generating recommendations.");
                return;
            }

            addBatch(data);

            considered = data.considered || considered;
            seenIds = data.seen_ids || seenIds;
            roundIdx += 1;

            if (data.empty) {
                // showError hides the summary card and surfaces the message.
                showError("Couldn’t find any new vinyl recommendations — try again.");
                return;
            }
            if (data.done) {
                showSpinner(false);
                showMore(false);
                setMetaTime();
                return;
            }
            // More rounds to go — show the footer and keep streaming.
            showMore(true);
            fetchBatch();
        }).catch(function() {
            finishOrError("Something went wrong generating recommendations.");
        });
    }

    // Show the (blank) Recommendations card and spinner up front so the page
    // indicates the search is underway; the "N releases" line stays hidden until
    // the first batch resolves.
    if (summary) summary.hidden = false;
    showSpinner(true);
    fetchBatch();
})();
