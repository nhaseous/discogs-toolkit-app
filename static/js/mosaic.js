// ==========================================================
// mosaic.js — Shared mosaic UI used by Price Checker and Lookup:
//   - buildItem / populate: mosaic-item DOM (thumb wrapped in <a> or <span>)
//   - slideIn / switchMosaics: slide-from-left animation, also tab swap
//   - attachSticky: detach mosaic into a sticky header on scroll-past
// Must load before pricechecker.js / lookup-browse.js / lookup.js.
// ==========================================================
(function() {
    var EASE = "transform 0.35s cubic-bezier(0.4,0,0.2,1), opacity 0.28s ease";
    var SLIDE_TRANSITION = "transform 0.35s cubic-bezier(0.4,0,0.2,1)";

    // Build a single mosaic-item (anchor or span) wrapping a lazy thumb.
    // opts:
    //   thumb     image src (required)
    //   tag       'a' | 'span' (default: 'a' if anchorId/url given, else 'span')
    //   anchorId  fragment target -> href="#id" (takes precedence over url)
    //   url       external URL -> href=url target=_blank rel=noopener
    //   index     sets data-index on the element
    //   reveal    if true, fire 'is-loaded' class on img load/error
    function buildItem(opts) {
        var tag = opts.tag || ((opts.anchorId || opts.url) ? 'a' : 'span');
        var el = document.createElement(tag);
        el.className = 'mosaic-item';
        if (tag === 'a') {
            if (opts.anchorId) {
                el.href = '#' + opts.anchorId;
            } else {
                el.href = opts.url || '#';
                el.target = '_blank';
                el.rel = 'noopener noreferrer';
            }
        }
        if (opts.index != null) el.setAttribute('data-index', opts.index);
        var img = document.createElement('img');
        img.className = 'mosaic-thumb';
        img.alt = '';
        img.setAttribute('loading', 'lazy');
        if (opts.reveal) {
            var fire = function() { img.classList.add('is-loaded'); };
            img.addEventListener('load', fire);
            img.addEventListener('error', fire);
            img.src = opts.thumb;
            if (img.complete && img.naturalWidth > 0) fire();
        } else {
            img.src = opts.thumb;
        }
        el.appendChild(img);
        return el;
    }

    // Populate a mosaic container with items. Each item needs `thumb` (falsy
    // = skipped); `url` is used when rendering as an anchor.
    // opts:
    //   tag    force 'a' or 'span' for all items (default: per-item)
    //   clear  false to append rather than replace (default: true)
    function populate(mosaicEl, items, opts) {
        opts = opts || {};
        if (!mosaicEl) return;
        if (opts.clear !== false) mosaicEl.innerHTML = '';
        var forcedTag = opts.tag;
        items.forEach(function(m) {
            if (!m.thumb) return;
            mosaicEl.appendChild(buildItem({
                thumb: m.thumb,
                url: forcedTag === 'span' ? null : m.url,
                tag: forcedTag,
            }));
        });
    }

    // Slide a mosaic in from the left (translateX(-w) -> 0).
    // opts.clipEl gets overflow:hidden for the duration so the slide
    // doesn't bleed outside its column.
    function slideIn(mosaicEl, opts) {
        opts = opts || {};
        var w = mosaicEl.offsetWidth;
        var clip = opts.clipEl;
        if (clip) clip.style.overflow = "hidden";
        mosaicEl.style.transition = "none";
        mosaicEl.style.transform = "translateX(-" + w + "px)";
        mosaicEl.style.opacity = "0";
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                mosaicEl.style.transition = EASE;
                mosaicEl.style.transform = "translateX(0)";
                mosaicEl.style.opacity = "1";
                mosaicEl.addEventListener("transitionend", function cleanup(e) {
                    if (e.propertyName !== "transform") return;
                    mosaicEl.removeEventListener("transitionend", cleanup);
                    mosaicEl.style.transition = "";
                    mosaicEl.style.transform = "";
                    mosaicEl.style.opacity = "";
                    if (clip) clip.style.overflow = "";
                });
            });
        });
    }

    // Animated tab-swap between two mosaics. Outgoing slides out left,
    // incoming slides in from left. Either may be null. `wrap` is given
    // a temporary min-height during the swap to keep layout from jumping.
    function switchMosaics(opts) {
        var incoming = opts.incoming;
        var outgoing = opts.outgoing;
        var wrap = opts.wrap;
        var inactiveClass = opts.inactiveClass || 'mosaic--inactive';
        if (!wrap) return;
        var w = wrap.offsetWidth;

        if (outgoing) {
            if (incoming) wrap.style.minHeight = outgoing.offsetHeight + "px";
            else wrap.style.minHeight = "";

            outgoing.classList.add(inactiveClass);
            outgoing.style.visibility = "visible";
            outgoing.style.transition = EASE;
            outgoing.style.transform = "translateX(-" + w + "px)";
            outgoing.style.opacity = "0";
            outgoing.addEventListener("transitionend", function cleanup(e) {
                if (e.propertyName !== "transform") return;
                outgoing.removeEventListener("transitionend", cleanup);
                outgoing.style.visibility = "";
                outgoing.style.transition = "";
                outgoing.style.transform = "";
                outgoing.style.opacity = "";
                if (!incoming) wrap.style.minHeight = "";
            });
        }

        if (incoming) {
            incoming.classList.remove(inactiveClass);
            incoming.style.transition = "none";
            incoming.style.transform = "translateX(-" + w + "px)";
            incoming.style.opacity = "0";
            requestAnimationFrame(function() {
                requestAnimationFrame(function() {
                    incoming.style.transition = EASE;
                    incoming.style.transform = "translateX(0)";
                    incoming.style.opacity = "1";
                    incoming.addEventListener("transitionend", function done(e) {
                        if (e.propertyName !== "transform") return;
                        incoming.removeEventListener("transitionend", done);
                        incoming.style.transition = "";
                        incoming.style.transform = "";
                        incoming.style.opacity = "";
                        wrap.style.minHeight = "";
                    });
                });
            });
        } else if (!outgoing) {
            wrap.style.minHeight = "";
        }
    }

    // Detach a mosaic into a body-level sticky header when scrolled out
    // of view; slide it back when the page scrolls back to returnEl.
    // opts:
    //   container        gets 'sticky-mosaic-active' class while sticky
    //   leftAnchorEl     sticky.left = leftAnchorEl.right + 48
    //   returnEl         re-entering view -> remove sticky + reveal
    //   clipEl           passed to slideIn for the reveal animation
    //   onStickyCreated  called after items are cloned; may return an
    //                    array of MutationObservers to disconnect later
    function attachSticky(mosaicEl, opts) {
        if (!mosaicEl || !opts || !opts.container) return;
        var container = opts.container;
        var leftAnchorEl = opts.leftAnchorEl;
        var returnEl = opts.returnEl;
        var sticky = null;
        var syncObservers = [];
        function reposition() {
            if (!sticky || !leftAnchorEl) return;
            sticky.style.left = leftAnchorEl.getBoundingClientRect().right + 48 + "px";
        }
        function activate() {
            if (sticky) return;
            sticky = document.createElement("div");
            sticky.id = "sticky-mosaic";
            mosaicEl.querySelectorAll(".mosaic-item").forEach(function(item) {
                sticky.appendChild(item.cloneNode(true));
            });
            if (opts.onStickyCreated) {
                var extra = opts.onStickyCreated(sticky);
                if (Array.isArray(extra)) syncObservers = syncObservers.concat(extra);
            }
            document.body.appendChild(sticky);
            reposition();
            window.addEventListener("resize", reposition);
            container.classList.add("sticky-mosaic-active");
            sticky.style.transform = "translateY(-100%)";
            requestAnimationFrame(function() {
                requestAnimationFrame(function() {
                    if (!sticky) return;
                    sticky.style.transition = SLIDE_TRANSITION;
                    sticky.style.transform = "translateY(0)";
                });
            });
        }
        function reveal() {
            container.classList.remove("sticky-mosaic-active");
            slideIn(mosaicEl, { clipEl: opts.clipEl });
        }
        function deactivate() {
            if (!sticky) return;
            syncObservers.forEach(function(mo) { mo.disconnect(); });
            syncObservers = [];
            window.removeEventListener("resize", reposition);
            var el = sticky;
            sticky = null;
            el.style.transition = SLIDE_TRANSITION;
            el.style.transform = "translateY(-100%)";
            el.addEventListener("transitionend", function() { el.remove(); reveal(); }, { once: true });
        }
        new IntersectionObserver(function(entries) {
            if (!entries[0].isIntersecting && entries[0].boundingClientRect.top < 0) { activate(); }
        }).observe(mosaicEl);
        if (returnEl) {
            new IntersectionObserver(function(entries) {
                if (!entries[0].isIntersecting) return;
                if (sticky) { deactivate(); return; }
                if (!container.classList.contains("sticky-mosaic-active")) return;
                reveal();
            }).observe(returnEl);
        }
        slideIn(mosaicEl, { clipEl: opts.clipEl });
    }

    window.Mosaic = {
        EASE: EASE,
        buildItem: buildItem,
        populate: populate,
        slideIn: slideIn,
        switchMosaics: switchMosaics,
        attachSticky: attachSticky,
    };
})();
