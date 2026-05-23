// ==========================================================
// insights.js — Insights Dashboard panel-toggle behavior:
//   3-state Year/Added/Genre card (.insights-three-toggle) with dynamic
//   try-merge of Added History under the Year pie; Sub-Genres/Genres toggle
//   (.insights-genre-toggle); Format Breakdown More/Less (.insights-format-toggle).
// Loaded by templates/lookup.html.
// ==========================================================
document.addEventListener("DOMContentLoaded", function() {
    document.querySelectorAll(".insights-three-toggle").forEach(function(wrap) {
        // Panels live in a CSS grid (all in grid-row:1, grid-column:1) so they stack
        // and the card height = max of all panels (and is stretched to the sibling
        // Format card via the flex row). We toggle with visibility, not display, so
        // panels keep their grid space and stay measurable while hidden.
        //
        // sizeScroll() sizes the Added panel's scroll area in the un-merged (toggle)
        // layout. tryMerge() runs once on load: if the card has enough slack beneath
        // the Year pie, it relocates Added History (subheader + graph + table) under
        // the pie and collapses the card to a 2-state Year+Added <-> Genre toggle.
        var sizeScroll = function() {
            if (wrap._locked) return;
            var ap = wrap.querySelector(":scope>[data-panel='added']");
            if (!ap) return;
            var sc = ap.querySelector(".insights-added-scroll");
            if (sc) { sc.style.maxHeight = "0"; sc.style.overflow = "hidden"; }
            var wh = wrap.offsetHeight, th = 34, gh = 82;
            var t = ap.querySelector(".rec-breakdown-title");
            var g = ap.querySelector(".insights-line-graph-wrap");
            if (t) th = t.offsetHeight + 10;
            if (g) gh = g.offsetHeight + 10;
            if (wh > 0) {
                if (sc) { sc.style.maxHeight = Math.max(60, wh - th - gh) + "px"; sc.style.overflow = ""; sc.style.overflowY = "auto"; }
                wrap._locked = true;
                var yp = wrap.querySelector(":scope>[data-panel='year']");
                if (yp) yp.classList.add("year-pie-centered");
            }
        };
        (function tryMerge() {
            var wrapH = wrap.offsetHeight;
            if (wrapH <= 0) { sizeScroll(); return; }
            var yearPanel = wrap.querySelector(":scope>[data-panel='year']");
            var addedPanel = wrap.querySelector(":scope>[data-panel='added']");
            var yPieSvg = yearPanel ? yearPanel.querySelector(".rec-pie-wrap svg") : null;
            if (!yearPanel || !addedPanel || !yPieSvg) { sizeScroll(); return; }
            var yTitle = yearPanel.querySelector(".rec-breakdown-title");
            var yPieWrap = yearPanel.querySelector(".rec-pie-wrap");
            var gWrap = addedPanel.querySelector(".insights-line-graph-wrap");
            var scrollEl = addedPanel.querySelector(".insights-added-scroll");
            var firstRow = scrollEl ? scrollEl.querySelector("tr") : null;
            var yTitleH = yTitle ? yTitle.offsetHeight : 34;
            var yPieH = yPieWrap ? yPieWrap.offsetHeight : 0;
            var gSvg = gWrap ? gWrap.querySelector("[data-vh]") : null;
            var gVH = gSvg ? parseFloat(gSvg.dataset.vh || "106") : 106;
            var fixedH = Math.round(gVH * 13 / 9);
            var graphH = gWrap ? Math.min(gWrap.offsetHeight, fixedH) : fixedH;
            var rowH = firstRow ? firstRow.offsetHeight : 30;
            // Measure the card height with the Added panel pulled OUT of the grid, so the
            // full table no longer dictates the card size. The card then reflects the year
            // pie / genre panel / sibling Format card, and we fit as many rows as fit into
            // the slack (scrolling the rest) instead of growing the card to show every row.
            // graphH/rowH are read above while the panel is still laid out.
            addedPanel.style.display = "none";
            var cardH = wrap.offsetHeight;
            addedPanel.style.display = "";
            var available = cardH - yTitleH - yPieH;
            // HEAD = title's 10px bottom margin + sub-label height (~14px) + sub-label
            // margin-bottom (3px). Sub-label margin-top is `auto` in the flex-column year
            // panel (resolves to 0 at minimum), so it no longer adds to the minimum HEAD.
            var HEAD = 27;
            // Require room for the subheader + graph. The scroll always shows at least one
            // row (Math.max(rowH,...) below); when the slack is just short of one row the
            // card grows by at most one row height. With more slack we show more rows and
            // the card is unchanged. If even subheader+graph won't fit, growing would be too
            // much — keep the secondary toggle instead.
            if (available < HEAD + graphH) { sizeScroll(); return; }
            var sub = document.createElement("div");
            sub.className = "insights-format-sub insights-format-sub--lower";
            sub.textContent = "Added History";
            yearPanel.appendChild(sub);
            var body = document.createElement("div");
            body.className = "insights-added-body";
            if (gWrap) body.appendChild(gWrap);
            if (scrollEl) body.appendChild(scrollEl);
            yearPanel.appendChild(body);
            if (addedPanel.parentNode) addedPanel.parentNode.removeChild(addedPanel);
            var addedBtn = yearPanel.querySelector(".insights-toggle-switch[data-goto='added']");
            if (addedBtn && addedBtn.parentNode) addedBtn.parentNode.removeChild(addedBtn);
            // Genre Breakdown stays the default-open panel (server-rendered default); the
            // merged Year+Added panel is reached via its "/ Year" toggle.
            // Clear any inline overflow/maxHeight set by sizeScroll() so the CSS rules
            // for .insights-added-body > .insights-added-scroll take over (max-height and
            // overflow-y are set there to match the fixed graph height).
            requestAnimationFrame(function() {
                if (scrollEl) { scrollEl.style.maxHeight = ""; scrollEl.style.overflow = ""; scrollEl.style.overflowY = ""; }
            });
            wrap._locked = true; wrap._merged = true;
        })();
        wrap.querySelectorAll(".insights-toggle-switch").forEach(function(btn) {
            btn.addEventListener("click", function() {
                var target = btn.dataset.goto;
                sizeScroll();
                // When navigating TO the genre panel, update its back-toggle to reflect
                // the source panel so "/ Year" vs "/ Added" is always contextually correct.
                if (target === "genre") {
                    var src = null;
                    wrap.querySelectorAll(":scope>.insights-panel").forEach(function(p) {
                        if (p.style.visibility !== "hidden") src = p.dataset.panel;
                    });
                    if (src) {
                        var gb = wrap.querySelector(":scope>[data-panel='genre'] .insights-genre-back");
                        if (gb) { gb.dataset.goto = src; gb.textContent = src === "year" ? "/ Year" : "/ Added"; }
                    }
                }
                wrap.querySelectorAll(":scope>.insights-panel").forEach(function(p) {
                    var active = p.dataset.panel === target;
                    p.style.visibility = active ? "" : "hidden";
                    p.style.pointerEvents = active ? "" : "none";
                });
            });
        });
    });
    // Delegated handlers — let lazy-injected wantlist insights work without re-binding.
    document.addEventListener("click", function(e) {
        var genreBtn = e.target.closest(".insights-genre-toggle .insights-toggle-switch");
        if (genreBtn) {
            var gWrap = genreBtn.closest(".insights-genre-toggle");
            if (gWrap) {
                gWrap.querySelectorAll(".insights-panel").forEach(function(p) {
                    p.style.display = p.style.display === "none" ? "" : "none";
                });
            }
            return;
        }
        var fmtBtn = e.target.closest(".insights-format-toggle .insights-toggle-switch");
        if (fmtBtn) {
            var fWrap = fmtBtn.closest(".insights-format-toggle");
            if (fWrap) {
                fWrap.querySelectorAll(".insights-format-panels-wrap>.insights-panel").forEach(function(p) {
                    var hidden = p.style.visibility === "hidden";
                    p.style.visibility = hidden ? "" : "hidden";
                    p.style.pointerEvents = hidden ? "" : "none";
                });
                fmtBtn.textContent = fmtBtn.textContent === "More" ? "Less" : "More";
            }
        }
    });
});
