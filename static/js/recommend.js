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
    var noteEl = document.getElementById("recommend-note");
    var errEl = document.getElementById("recommend-error");
    var refreshBtn = document.getElementById("recommend-refresh");
    var metaTime = document.getElementById("recommend-meta-time");

    var considered = [];     // [{artist, album}] round-tripped to avoid repeats
    var seenIds = [];        // resolved release IDs round-tripped to dedupe
    var roundIdx = 0;
    var cardEls = [];        // all rendered card nodes, in insertion order
    var startTime = Date.now();
    var busy = false;        // a batch round is in flight
    var GENERIC_ERR = "Something went wrong generating recommendations.";

    function showSpinner(on) { if (spinner) spinner.style.display = on ? "block" : "none"; }
    function showMore(on) { if (moreEl) moreEl.hidden = !on; }
    function showRefresh(on) { if (refreshBtn) refreshBtn.hidden = !on; }
    function setBusy(on) { busy = on; if (refreshBtn) refreshBtn.disabled = on; }
    function showNote(msg) { if (noteEl) { noteEl.textContent = msg; noteEl.hidden = false; } }
    function hideNote() { if (noteEl) noteEl.hidden = true; }

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

    // A manual refresh ended (empty result, cap, or error): keep the cards we
    // have, drop the footer spinner, and surface a brief inline note. The refresh
    // control comes back so the user can try again.
    function manualStop(msg) {
        showMore(false);
        setMetaTime();
        showNote(msg);
        showRefresh(true);
    }

    // Run ONE batch round. `auto` drives the initial streaming load (keeps going
    // until the server says done); a manual refresh (`auto` false) runs a single
    // round, shows only the bottom spinner, and never re-shows the top one.
    function postBatch(auto) {
        setBusy(true);
        fetch("/recommend/batch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user: user,
                new_artists: newArtists,
                considered: considered,
                seen_ids: seenIds,
                have: cardEls.length,
                round: roundIdx,
                manual: !auto   // refresh clicks over-ask Gemini; initial rounds don't
            })
        }).then(function(r) {
            return r.json().catch(function() { throw new Error("bad_json"); });
        }).then(function(data) {
            setBusy(false);
            if (data.error) {
                if (auto) finishOrError(data.message || GENERIC_ERR);
                else manualStop(data.message || GENERIC_ERR);
                return;
            }

            var before = cardEls.length;
            addBatch(data);
            considered = data.considered || considered;
            seenIds = data.seen_ids || seenIds;
            roundIdx += 1;
            var added = cardEls.length - before;

            // Only possible on the initial run (a manual refresh always has cards
            // already, so total > 0): nothing found across the whole search.
            if (data.empty) {
                showError("Couldn’t find any new vinyl recommendations — try again.");
                return;
            }
            // Initial stream with more rounds to go — show the footer, keep going.
            if (auto && !data.done) {
                showMore(true);
                postBatch(true);
                return;
            }

            // Initial stream finished, or a manual round completed.
            showSpinner(false);
            showMore(false);
            setMetaTime();
            // A manual round that resolved no new cards: brief inline note.
            if (!auto && added === 0) {
                showNote("No new picks right now — try again later.");
            }
            showRefresh(true);
        }).catch(function() {
            setBusy(false);
            if (auto) finishOrError(GENERIC_ERR);
            else manualStop(GENERIC_ERR);
        });
    }

    // Manual "get more": one extra Gemini round, bottom spinner only.
    if (refreshBtn) {
        refreshBtn.addEventListener("click", function() {
            if (busy) return;
            hideNote();
            showMore(true);       // bottom spinner; top spinner stays hidden
            startTime = Date.now();
            postBatch(false);
        });
    }

    // Show the (blank) Recommendations card and spinner up front so the page
    // indicates the search is underway; the "N releases" line stays hidden until
    // the first batch resolves.
    if (summary) summary.hidden = false;
    showSpinner(true);
    postBatch(true);
})();
