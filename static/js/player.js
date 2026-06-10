// ==========================================================
// player.js — Lookup in-app Apple Music preview player.
//   Clicking a card's play button (.match-card-play) resolves the
//   release to an Apple Music album via /player/resolve, loads the
//   native Apple embed into the fixed right rail (#player-rail), and
//   swaps the sidebar's spinning platter for the album cover. The
//   platter doubles as the "Export PDF" button (main.js), so hiding
//   it while the player is open removes that button until dismissed;
//   closing the player reverts both.
// Loaded only on the Lookup page (after main.js).
// ==========================================================

(function() {
    var rail = document.getElementById("player-rail");
    if (!rail) return;                       // no results / not the lookup page

    var frame = document.getElementById("player-rail-frame");
    var label = document.getElementById("player-rail-label");
    var closeBtn = document.getElementById("player-rail-close");
    var platter = document.querySelector(".sidebar-platter");
    var cover = document.querySelector(".sidebar-nowplaying");

    var activeBtn = null;   // the play button of the currently-loaded release
    var reqSeq = 0;         // ignore stale resolves when play buttons are clicked fast

    function setLoading(btn, on) {
        if (!btn) return;
        btn.classList.toggle("match-card-play--loading", on);
        btn.disabled = on;
    }

    function flashNotFound(btn) {
        if (!btn) return;
        btn.classList.add("match-card-play--notfound");
        btn.setAttribute("title", "Not on Apple Music");
        setTimeout(function() {
            btn.classList.remove("match-card-play--notfound");
            btn.setAttribute("title", "Play preview on Apple Music");
        }, 2500);
    }

    // Swap the sidebar platter (also the PDF-export button) for the album cover.
    function showCover(artwork) {
        if (platter) platter.style.display = "none";
        if (cover && artwork) {
            cover.src = artwork;
            cover.hidden = false;
        }
    }
    function restorePlatter() {
        if (platter) platter.style.display = "";
        if (cover) { cover.hidden = true; cover.src = ""; }
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

    // Reserving side space for the rail narrows the content, but grid.js only
    // recolumnizes on window resize — so reflow the card grid explicitly after
    // the margin animates in/out, otherwise cards overflow the new width.
    function reflowGrid() {
        if (window._layoutMatchGrids) window._layoutMatchGrids();
    }
    function reflowAfterTransition() {
        reflowGrid();                        // progressive pass during the animation
        setTimeout(reflowGrid, 260);         // final pass once the 0.22s margin settles
    }

    function openRail() {
        var wasOpen = !rail.hidden;
        rail.hidden = false;
        document.documentElement.classList.add("player-open");
        // Next frame so the transition runs from the hidden state.
        requestAnimationFrame(function() { rail.classList.add("player-rail--open"); });
        if (!wasOpen) reflowAfterTransition();   // only the first open changes width
    }

    function closeRail() {
        rail.classList.remove("player-rail--open");
        rail.hidden = true;
        document.documentElement.classList.remove("player-open");
        frame.innerHTML = "";                // stop playback
        restorePlatter();
        if (activeBtn) activeBtn.classList.remove("match-card-play--active");
        activeBtn = null;
        reflowAfterTransition();
    }

    function play(btn) {
        var artist = btn.getAttribute("data-artist") || "";
        var title = btn.getAttribute("data-title") || "";
        var seq = ++reqSeq;
        setLoading(btn, true);

        ToolkitAPI.resolvePlayer(artist, title).then(function(data) {
            if (seq !== reqSeq) return;      // a newer click superseded this one
            setLoading(btn, false);
            if (!data || !data.found) { flashNotFound(btn); return; }

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
            flashNotFound(btn);
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

    if (closeBtn) closeBtn.addEventListener("click", closeRail);
    document.addEventListener("keydown", function(e) {
        if (e.key === "Escape" && !rail.hidden) closeRail();
    });
})();
