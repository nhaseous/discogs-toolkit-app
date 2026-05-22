// ==========================================================
// grid.js — shared card-grid behavior used by Matcher AND Lookup:
//   window._layoutMatchGrids (responsive column layout) and
//   window._resetMatchCardHover (match-card hover sequencing).
// Loaded by matcher.html and lookup pages, after main.js.
// ==========================================================

(function() {
    // Align thumbnails across columns when cards are collapsed. The art is a
    // fixed square and the body is collapsed (height 0), so the only variable
    // in a card's collapsed height is its info block (artist + title). Rather
    // than inflate the info block — which would add space between the title and
    // the body — we push the slack BELOW each card via margin-bottom, keeping
    // the title→format gap constant. margin-bottom is measured from the info
    // height, which never changes between collapsed/expanded, so this is safe
    // to run in either state.
    function equalizeCardRows(grid) {
        var cols = Array.from(grid.querySelectorAll('.match-column'));
        if (!cols.length) return;
        var numRows = Math.max.apply(null, cols.map(function(c) { return c.children.length; }));
        for (var row = 0; row < numRows; row++) {
            var items = [];
            cols.forEach(function(col) {
                var card = col.children[row];
                if (card) {
                    card.style.marginBottom = '';
                    var info = card.querySelector('.match-card-info');
                    if (info) { info.style.minHeight = ''; items.push({ card: card, info: info }); }
                }
            });
            if (!items.length) continue;
            var maxH = Math.max.apply(null, items.map(function(o) { return o.info.offsetHeight; }));
            items.forEach(function(o) {
                var delta = maxH - o.info.offsetHeight;
                o.card.style.marginBottom = delta ? delta + 'px' : '';
            });
        }
    }

    function layoutMatchGrid(grid) {
        if (!grid.offsetParent) return;
        var allCards = Array.from(grid.querySelectorAll(".match-card"));
        if (!allCards.length) return;
        var gap = 14, minWidth = 158;
        var numCols = Math.max(1, Math.floor((grid.offsetWidth + gap) / (minWidth + gap)));
        var existing = Array.from(grid.children);
        if (existing.length === numCols && existing.every(function(c) { return c.classList.contains("match-column"); })) {
            equalizeCardRows(grid);
            return;
        }
        grid.innerHTML = "";
        var cols = [];
        for (var i = 0; i < numCols; i++) {
            var col = document.createElement("div");
            col.className = "match-column";
            grid.appendChild(col);
            cols.push(col);
        }
        allCards.forEach(function(c, i) { cols[i % numCols].appendChild(c); });
        equalizeCardRows(grid);
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
