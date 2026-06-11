// ==========================================================
// player.js — Lookup in-app Apple Music preview player.
//   Clicking a card's play button (.match-card-play) resolves the
//   release to an Apple Music album via /player/resolve, loads the
//   native Apple embed into the fixed right rail (#player-rail), and
//   slides the album cover in over the sidebar's spinning platter.
//   The platter doubles as the "Export PDF" button (main.js); while a
//   cover is shown it sits on top and intercepts clicks, so that button
//   is suppressed until the cover slides back out on close.
// Loaded only on the Lookup page (after main.js).
// ==========================================================

(function() {
    var rail = document.getElementById("player-rail");
    if (!rail) return;                       // no results / not the lookup page

    var frame = document.getElementById("player-rail-frame");
    var label = document.getElementById("player-rail-label");
    var closeBtn = document.getElementById("player-rail-close");
    var cover = document.querySelector(".sidebar-nowplaying");

    var activeBtn = null;   // the play button of the currently-loaded release
    var reqSeq = 0;         // ignore stale resolves when play buttons are clicked fast
    var coverSwapTimer = null;   // pending cover slide-out→in when switching releases

    function setLoading(btn, on) {
        if (!btn) return;
        btn.classList.toggle("match-card-play--loading", on);
        btn.disabled = on;
    }

    // Show a text message in the rail, in the same place the player would load
    // (e.g. when a release has no Apple Music match). Resets any now-playing state.
    function showMessage(artist, title, text) {
        if (activeBtn) activeBtn.classList.remove("match-card-play--active");
        activeBtn = null;
        restorePlatter();
        label.textContent = (artist ? artist + " — " : "") + title;
        frame.innerHTML = '<div class="player-rail-message"></div>';
        frame.firstChild.textContent = text;
        openRail();
    }

    // Slide the album cover in over the sidebar platter while a track is loaded,
    // and slide it back out (revealing the spinning platter / PDF-export button)
    // on close. The cover stays in the DOM at its faded-out state between plays so
    // the slide can animate both directions.
    function slideCoverIn(artwork) {
        cover.src = artwork;
        cover.hidden = false;
        // Force the out-state to apply before transitioning in — needed on the
        // first show, where the element starts at display:none.
        void cover.offsetWidth;
        cover.classList.add("sidebar-nowplaying--in");
    }
    function showCover(artwork) {
        if (!cover || !artwork) return;
        clearTimeout(coverSwapTimer);
        // Already showing a cover (switching releases): slide the current one out,
        // then swap the art and slide the new one in — same animation as the first
        // show, so it reads like putting a new record on.
        if (!cover.hidden && cover.classList.contains("sidebar-nowplaying--in")) {
            cover.classList.remove("sidebar-nowplaying--in");        // slide current out
            coverSwapTimer = setTimeout(function() {
                slideCoverIn(artwork);                              // slide the new one in
            }, 300);                                                // matches the 0.3s CSS transition
            return;
        }
        slideCoverIn(artwork);
    }
    function restorePlatter() {
        clearTimeout(coverSwapTimer);
        if (cover) cover.classList.remove("sidebar-nowplaying--in");
    }

    function loadEmbed(embedUrl) {
        var iframe = document.createElement("iframe");
        iframe.src = embedUrl;
        iframe.allow = "autoplay *; encrypted-media *; clipboard-write";
        iframe.setAttribute("sandbox",
            "allow-forms allow-popups allow-same-origin allow-scripts " +
            "allow-storage-access-by-user-activation allow-top-navigation-by-user-activation");
        iframe.setAttribute("frameborder", "0");
        iframe.loading = "lazy";
        frame.innerHTML = "";
        frame.appendChild(iframe);
    }

    // Size the rail to the leftover whitespace to the RIGHT of the main content,
    // computed when it opens (and on resize / sidebar toggle). Only the player's
    // width changes — the main content is never resized to make room. When there's
    // enough room the player sits in the gap beside the content; when there isn't
    // (narrow desktop) it floats over the content's right edge; below 900px the
    // CSS bottom-dock takes over, so inline sizing is cleared.
    var GAP = 24, MIN_W = 280, MAX_W = 420;
    function sizeRail() {
        if (rail.hidden) return;
        // Mobile: no room beside the content — dock to the bottom of the screen.
        if (window.innerWidth <= 900) {
            rail.classList.add("player-rail--docked");
            rail.style.left = rail.style.right = rail.style.width = "";
            return;
        }
        // Desktop: sit beside the content (constant GAP on the left) and run flush
        // to the screen's right edge. When the gap is tighter than MIN_W, keep
        // MIN_W and allow the slight overlap rather than docking — tuned by eye.
        rail.classList.remove("player-rail--docked");
        var content = document.querySelector(".content");
        if (!content) return;
        var contentRight = content.getBoundingClientRect().right;
        var avail = window.innerWidth - contentRight;
        rail.style.width = Math.max(MIN_W, Math.min(avail - GAP, MAX_W)) + "px";
        rail.style.right = "0";
        rail.style.left = "auto";
    }

    function openRail() {
        rail.hidden = false;
        sizeRail();              // fit the width to the available space before it shows
        // Next frame so the transition runs from the hidden state.
        requestAnimationFrame(function() { rail.classList.add("player-rail--open"); });
    }

    function closeRail() {
        rail.classList.remove("player-rail--open");
        rail.hidden = true;
        frame.innerHTML = "";                // stop playback
        restorePlatter();
        if (activeBtn) activeBtn.classList.remove("match-card-play--active");
        activeBtn = null;
    }

    function play(btn) {
        var artist = btn.getAttribute("data-artist") || "";
        var title = btn.getAttribute("data-title") || "";
        var seq = ++reqSeq;
        setLoading(btn, true);

        ToolkitAPI.resolvePlayer(artist, title).then(function(data) {
            if (seq !== reqSeq) return;      // a newer click superseded this one
            setLoading(btn, false);
            if (!data || !data.found) {
                showMessage(artist, title, "Couldn’t find this release on Apple Music.");
                return;
            }

            if (activeBtn && activeBtn !== btn) activeBtn.classList.remove("match-card-play--active");
            activeBtn = btn;
            btn.classList.add("match-card-play--active");

            label.textContent = (artist ? artist + " — " : "") + title;
            loadEmbed(data.embed_url);
            showCover(data.artwork);
            openRail();
        }).catch(function() {
            if (seq !== reqSeq) return;
            setLoading(btn, false);
            showMessage(artist, title, "Couldn’t reach Apple Music. Please try again.");
        });
    }

    // Capture on `window` so this runs before main.js's document-level capture
    // handler (which would otherwise treat the click as the card's external
    // Discogs link inside the desktop app) and before the card's own navigation.
    window.addEventListener("click", function(e) {
        var btn = e.target.closest ? e.target.closest(".match-card-play") : null;
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();
        if (e.stopImmediatePropagation) e.stopImmediatePropagation();
        play(btn);
    }, true);

    // Card navigation policy: a lookup release card opens its Discogs release only
    // when the click lands on its art (thumbnail) or its info (artist/title).
    // Clicks anywhere else on the card — the format row with the play button,
    // comments, stats, empty space — do NOT navigate, so the body is a safe place
    // to interact without being thrown to Discogs. List-index cards have no
    // .match-card-info (their title lives in the body), so they're left alone and
    // keep navigating as normal. The play button and the "for sale" pill stop their
    // own clicks, so they never reach here.
    document.addEventListener("click", function(e) {
        var card = e.target.closest(".match-card");
        if (!card || !card.querySelector(".match-card-info")) return;
        if (e.target.closest(".match-card-art") || e.target.closest(".match-card-info")) return;
        e.preventDefault();
    });

    if (closeBtn) closeBtn.addEventListener("click", closeRail);
    document.addEventListener("keydown", function(e) {
        if (e.key === "Escape" && !rail.hidden) closeRail();
    });

    // Re-fit the player when the layout shifts while it's open: the content's
    // right edge moves on window resize and when the sidebar collapses/expands
    // (its 0.22s transition — re-measure once it settles). sizeRail() no-ops when
    // the rail is closed, so these stay cheap.
    window.addEventListener("resize", sizeRail);
    var sidebarToggle = document.getElementById("sidebar-toggle");
    if (sidebarToggle) sidebarToggle.addEventListener("click", function() {
        setTimeout(sizeRail, 260);
    });
})();
