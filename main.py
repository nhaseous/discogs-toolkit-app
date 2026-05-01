from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request
from helper import pricechecker, matcher, lookup as lookup_helper
from concurrent.futures import ThreadPoolExecutor, as_completed
import cloudscraper, time, html as _html
from datetime import datetime
# Main

app = Flask(__name__)

with open('static/discogs-logo.svg') as _f:
    DISCOGS_LOGO_SVG = _f.read().strip()

with open('static/logo.svg') as _f:
    LOGO_SVG = _f.read().strip().replace('<svg ', '<svg class="brand-icon" ', 1)

VINYL_PLACEHOLDER_SVG = (
    '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="50" cy="50" r="46" fill="currentColor"/>'
    '<circle cx="50" cy="50" r="20" fill="var(--rule)"/>'
    '<circle cx="50" cy="50" r="4" fill="currentColor"/>'
    '</svg>'
)

SEARCH_ICON_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>'
)

_RATE_LIMIT_NOTICE = (
    '<div class="lookup-notice lookup-notice--error">'
    'Discogs is rate limiting requests right now. '
    'Please wait 60 seconds before you try again.'
    '</div>'
)

BACK_ARROW_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M19 12H5"/><path d="M12 5l-7 7 7 7"/></svg>'
)

EYE_CLOSED_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M3 12Q12 17 21 12"/>'
    '<line x1="3" y1="12" x2="1.5" y2="15"/>'
    '<line x1="7.5" y1="13.8" x2="6.8" y2="17.2"/>'
    '<line x1="12" y1="14.5" x2="12" y2="18"/>'
    '<line x1="16.5" y1="13.8" x2="17.2" y2="17.2"/>'
    '<line x1="21" y1="12" x2="22.5" y2="15"/>'
    '</svg>'
)

EYE_OPEN_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>'
    '<circle cx="12" cy="12" r="3"/>'
    '</svg>'
)

def page_layout(content, content_class="", show_platter=False, title="Discogs Toolkit"):
    path = request.path
    pc_active = ' class="active"' if path == '/pricechecker' else ''
    matcher_active = ' class="active"' if path == '/matcher' else ''
    lookup_active = ' class="active"' if path == '/lookup' else ''
    is_landing = path == '/'
    platter_img = '<img src="/static/platter.png" alt="" class="sidebar-platter">' if show_platter else ''
    sidebar_art = (
        '<div class="sidebar-art">'
        '<img src="/static/console-oak.png" alt="" class="sidebar-art-img">'
        + platter_img +
        '</div>'
    ) if not is_landing else ''
    return (
        '<!DOCTYPE html>'
        '<html lang="en">'
        '<head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>' + title + '</title>'
        '<link rel="icon" type="image/svg+xml" href="/static/logo.svg">'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;1,9..144,400;1,9..144,500'
        '&family=Inter:wght@400;500;600;700&display=swap">'
        '<link rel="stylesheet" href="/static/style.css?v=2">'
        '</head>'
        '<body>'
        '<div class="layout">'
        '<nav class="sidebar">'
        '<a href="/" class="sidebar-brand">'
        + LOGO_SVG +
        '<span class="brand-text"><span class="brand-discogs-logo">' + DISCOGS_LOGO_SVG + '</span>Toolkit</span>'
        '</a>'
        '<div class="sidebar-label">♪ Tools ♪</div>'
        '<a href="/pricechecker"' + pc_active + '>Price Checker</a>'
        '<a href="/matcher"' + matcher_active + '>Matcher</a>'
        '<a href="/lookup"' + lookup_active + '>Lookup</a>'
        + sidebar_art +
        '</nav>'
        '<main class="content' + (' ' + content_class if content_class else '') + '">'
        '<div id="content-main">'
    ) + content + (
        '</div>'
        '</main>'
        '</div>'
        '<div id="badge-tooltip"></div>'
        '<script>'
        'document.querySelectorAll(".sidebar a").forEach(function(link) {'
        '    link.addEventListener("click", function(e) {'
        '        if (this.pathname === window.location.pathname) {'
        '            e.preventDefault();'
        '            window.scrollTo({ top: 0, behavior: "smooth" });'
        '            history.replaceState(null, "", window.location.pathname + window.location.search);'
        '        }'
        '    });'
        '});'
        '(function() {'
        '    var active = new Set();'
        '    var pills = document.querySelectorAll(".inv-count-badge[data-filter]");'
        '    if (!pills.length) return;'
        '    pills.forEach(function(pill) {'
        '        pill.addEventListener("click", function() {'
        '            var f = this.getAttribute("data-filter");'
        '            if (active.has(f)) {'
        '                active.delete(f);'
        '                this.classList.remove("filter-active");'
        '                if (f === "low") {'
        '                    active.delete("lowest");'
        '                    var lb = document.querySelector(".inv-count-badge[data-filter=\'lowest\']");'
        '                    if (lb) lb.classList.remove("filter-active");'
        '                }'
        '            } else {'
        '                active.add(f);'
        '                this.classList.add("filter-active");'
        '                if (f === "lowest") {'
        '                    active.add("low");'
        '                    var lowb = document.querySelector(".inv-count-badge[data-filter=\'low\']");'
        '                    if (lowb) lowb.classList.add("filter-active");'
        '                }'
        '                if (f === "recent") {'
        '                    active.delete("old");'
        '                    var oldb = document.querySelector(".inv-count-badge[data-filter=\'old\']");'
        '                    if (oldb) oldb.classList.remove("filter-active");'
        '                }'
        '                if (f === "old") {'
        '                    active.delete("recent");'
        '                    var recentb = document.querySelector(".inv-count-badge[data-filter=\'recent\']");'
        '                    if (recentb) recentb.classList.remove("filter-active");'
        '                }'
        '            }'
        '            filter();'
        '        });'
        '    });'
        '    function filter() {'
        '        document.querySelectorAll(".result-card").forEach(function(card) {'
        '            if (!active.size) { card.style.display = ""; return; }'
        '            var cb = (card.getAttribute("data-badges") || "").split(" ");'
        '            var show = true;'
        '            active.forEach(function(f) { if (cb.indexOf(f) === -1) show = false; });'
        '            card.style.display = show ? "" : "none";'
        '        });'
        '        document.querySelectorAll(".sort-group-header").forEach(function(hdr) {'
        '            if (!active.size) { hdr.style.display = ""; return; }'
        '            var sib = hdr.nextElementSibling;'
        '            var vis = false;'
        '            while (sib && !sib.classList.contains("sort-group-header")) {'
        '                if (sib.classList.contains("result-card") && sib.style.display !== "none") { vis = true; break; }'
        '                sib = sib.nextElementSibling;'
        '            }'
        '            hdr.style.display = vis ? "" : "none";'
        '        });'
        '    }'
        '})();'
        '(function() {'
        '    var mosaic = document.getElementById("results-mosaic");'
        '    if (!mosaic) return;'
        '    var container = mosaic.closest(".content");'
        '    var sticky = null;'
        '    var syncObservers = [];'
        '    function reposition() {'
        '        if (!sticky) return;'
        '        sticky.style.left = document.getElementById("content-main").getBoundingClientRect().right + 48 + "px";'
        '    }'
        '    function activate() {'
        '        if (sticky) return;'
        '        sticky = document.createElement("div");'
        '        sticky.id = "sticky-mosaic";'
        '        mosaic.querySelectorAll(".mosaic-item").forEach(function(item) {'
        '            sticky.appendChild(item.cloneNode(true));'
        '        });'
        '        var invCount = mosaic.nextElementSibling;'
        '        if (invCount) {'
        '            var cloned = invCount.cloneNode(true);'
        '            cloned.querySelectorAll(".inv-count-badge[data-filter]").forEach(function(cb) {'
        '                cb.addEventListener("click", function(e) {'
        '                    e.stopPropagation();'
        '                    var orig = invCount.querySelector(".inv-count-badge[data-filter=\'" + this.getAttribute("data-filter") + "\']");'
        '                    if (orig) orig.click();'
        '                });'
        '            });'
        '            invCount.querySelectorAll(".inv-count-badge[data-filter]").forEach(function(ob) {'
        '                var mo = new MutationObserver(function() {'
        '                    var cb = cloned.querySelector(".inv-count-badge[data-filter=\'" + ob.getAttribute("data-filter") + "\']");'
        '                    if (cb) cb.classList.toggle("filter-active", ob.classList.contains("filter-active"));'
        '                });'
        '                mo.observe(ob, { attributes: true, attributeFilter: ["class"] });'
        '                syncObservers.push(mo);'
        '            });'
        '            sticky.appendChild(cloned);'
        '        }'
        '        document.body.appendChild(sticky);'
        '        reposition();'
        '        window.addEventListener("resize", reposition);'
        '        container.classList.add("sticky-mosaic-active");'
        '        sticky.style.transform = "translateY(-100%)";'
        '        requestAnimationFrame(function() {'
        '            requestAnimationFrame(function() {'
        '                if (!sticky) return;'
        '                sticky.style.transition = "transform 0.35s cubic-bezier(0.4,0,0.2,1)";'
        '                sticky.style.transform = "translateY(0)";'
        '            });'
        '        });'
        '    }'
        '    var MOSAIC_EASE = "transform 0.35s cubic-bezier(0.4,0,0.2,1), opacity 0.28s ease";'
        '    function slideInMosaic() {'
        '        var w = mosaic.offsetWidth;'
        '        var clip = document.getElementById("content-main");'
        '        if (clip) clip.style.overflow = "hidden";'
        '        mosaic.style.transition = "none";'
        '        mosaic.style.transform = "translateX(-" + w + "px)";'
        '        mosaic.style.opacity = "0";'
        '        requestAnimationFrame(function() {'
        '            requestAnimationFrame(function() {'
        '                mosaic.style.transition = MOSAIC_EASE;'
        '                mosaic.style.transform = "translateX(0)";'
        '                mosaic.style.opacity = "1";'
        '                mosaic.addEventListener("transitionend", function cleanup(e) {'
        '                    if (e.propertyName !== "transform") return;'
        '                    mosaic.removeEventListener("transitionend", cleanup);'
        '                    mosaic.style.transition = "";'
        '                    mosaic.style.transform = "";'
        '                    mosaic.style.opacity = "";'
        '                    if (clip) clip.style.overflow = "";'
        '                });'
        '            });'
        '        });'
        '    }'
        '    function revealMosaic() {'
        '        container.classList.remove("sticky-mosaic-active");'
        '        slideInMosaic();'
        '    }'
        '    function deactivate() {'
        '        if (!sticky) return;'
        '        syncObservers.forEach(function(mo) { mo.disconnect(); });'
        '        syncObservers = [];'
        '        window.removeEventListener("resize", reposition);'
        '        var el = sticky;'
        '        sticky = null;'
        '        el.style.transition = "transform 0.35s cubic-bezier(0.4,0,0.2,1)";'
        '        el.style.transform = "translateY(-100%)";'
        '        el.addEventListener("transitionend", function() { el.remove(); revealMosaic(); }, { once: true });'
        '    }'
        '    new IntersectionObserver(function(entries) {'
        '        if (!entries[0].isIntersecting && entries[0].boundingClientRect.top < 0) { activate(); }'
        '    }).observe(mosaic);'
        '    var invCount = mosaic.nextElementSibling;'
        '    if (invCount) {'
        '        new IntersectionObserver(function(entries) {'
        '            if (!entries[0].isIntersecting) return;'
        '            if (sticky) { deactivate(); return; }'
        '            if (!container.classList.contains("sticky-mosaic-active")) return;'
        '            revealMosaic();'
        '        }).observe(invCount);'
        '    }'
        '    slideInMosaic();'
        '})();'
        '(function() {'
        '    var tip = document.getElementById("badge-tooltip");'
        '    if (!tip) return;'
        '    document.querySelectorAll(".inv-count-badge[data-tooltip]").forEach(function(badge) {'
        '        badge.addEventListener("mouseenter", function(e) {'
        '            var s = window.getComputedStyle(this);'
        '            tip.textContent = this.getAttribute("data-tooltip");'
        '            tip.style.background = s.backgroundColor;'
        '            tip.style.color = s.color;'
        '            tip.style.left = e.clientX + "px";'
        '            tip.style.top = e.clientY + "px";'
        '            tip.style.display = "block";'
        '        });'
        '        badge.addEventListener("mousemove", function(e) {'
        '            tip.style.left = e.clientX + "px";'
        '            tip.style.top = e.clientY + "px";'
        '        });'
        '        badge.addEventListener("mouseleave", function() {'
        '            tip.style.display = "none";'
        '        });'
        '    });'
        '})();'
        '(function() {'
        '    function attachFormAnim(formId) {'
        '        var form = document.getElementById(formId);'
        '        if (!form) return;'
        '        form.addEventListener("submit", function(e) {'
        '            e.preventDefault();'
        '            form.nextElementSibling.style.display = "block";'
        '            var header = document.querySelector(".page-header");'
        '            if (header) {'
        '                var formRect = form.getBoundingClientRect();'
        '                var gap = parseInt(window.getComputedStyle(form).marginBottom) || 22;'
        '                var targetTop = 30;'
        '                var delta = targetTop - formRect.top;'
        '                if (delta < 0) {'
        '                    var headerShift = (targetTop + formRect.height + gap) - header.getBoundingClientRect().top;'
        '                    var ease = "transform 0.4s cubic-bezier(0.4,0,0.2,1)";'
        '                    form.style.transition = ease;'
        '                    form.style.transform = "translateY(" + delta + "px)";'
        '                    header.style.transition = ease;'
        '                    header.style.transform = "translateY(" + headerShift + "px)";'
        '                    form.addEventListener("transitionend", function() { form.submit(); }, { once: true });'
        '                    return;'
        '                }'
        '            }'
        '            requestAnimationFrame(function() { requestAnimationFrame(function() { form.submit(); }); });'
        '        });'
        '    }'
        '    attachFormAnim("pc-form");'
        '    attachFormAnim("matcher-form");'
        '    attachFormAnim("lookup-form");'
        '})();'
        '(function() {'
        '    function layoutMatchGrid(grid) {'
        '        var allCards = Array.from(grid.querySelectorAll(".match-card"));'
        '        if (!allCards.length) return;'
        '        var gap = 14, minWidth = 158;'
        '        var numCols = Math.max(1, Math.floor((grid.offsetWidth + gap) / (minWidth + gap)));'
        '        var existing = Array.from(grid.children);'
        '        if (existing.length === numCols && existing.every(function(c) { return c.classList.contains("match-column"); })) return;'
        '        grid.innerHTML = "";'
        '        var cols = [];'
        '        for (var i = 0; i < numCols; i++) {'
        '            var col = document.createElement("div");'
        '            col.className = "match-column";'
        '            grid.appendChild(col);'
        '            cols.push(col);'
        '        }'
        '        allCards.forEach(function(c, i) { cols[i % numCols].appendChild(c); });'
        '    }'
        '    window._layoutMatchGrids = function() {'
        '        document.querySelectorAll(".match-grid").forEach(layoutMatchGrid);'
        '    };'
        '    window._layoutMatchGrids();'
        '    var _lgTimer;'
        '    window.addEventListener("resize", function() {'
        '        clearTimeout(_lgTimer);'
        '        _lgTimer = setTimeout(window._layoutMatchGrids, 100);'
        '    });'
        '})();'
        '(function() {'
        '    var tabs = document.querySelectorAll(".lookup-tab");'
        '    if (!tabs.length) return;'
        '    var EASE = "transform 0.35s cubic-bezier(0.4,0,0.2,1), opacity 0.28s ease";'
        '    function animateOut(el, w, onDone) {'
        '        el.style.transition = EASE;'
        '        el.style.transform = "translateX(-" + w + "px)";'
        '        el.style.opacity = "0";'
        '        el.addEventListener("transitionend", function cleanup(e) {'
        '            if (e.propertyName !== "transform") return;'
        '            el.removeEventListener("transitionend", cleanup);'
        '            el.style.display = "none";'
        '            el.style.transition = ""; el.style.transform = ""; el.style.opacity = "";'
        '            if (onDone) onDone();'
        '        });'
        '    }'
        '    function animateIn(el, w, wrap) {'
        '        el.style.transition = "none";'
        '        el.style.transform = "translateX(-" + w + "px)";'
        '        el.style.opacity = "0";'
        '        el.style.display = "";'
        '        requestAnimationFrame(function() {'
        '            requestAnimationFrame(function() {'
        '                el.style.transition = EASE;'
        '                el.style.transform = "translateX(0)";'
        '                el.style.opacity = "1";'
        '                el.addEventListener("transitionend", function done(e) {'
        '                    if (e.propertyName !== "transform") return;'
        '                    el.removeEventListener("transitionend", done);'
        '                    el.style.transition = ""; el.style.transform = ""; el.style.opacity = "";'
        '                    if (wrap) wrap.style.minHeight = "";'
        '                });'
        '            });'
        '        });'
        '    }'
        '    function switchMosaics(target) {'
        '        var all = Array.from(document.querySelectorAll(".lookup-mosaic"));'
        '        var incoming = document.getElementById("lookup-mosaic-" + target);'
        '        var outgoing = all.find(function(m) { return m !== incoming && m.style.display !== "none"; });'
        '        if (!incoming && !outgoing) return;'
        '        var wrap = (outgoing || incoming).parentNode;'
        '        var w = wrap.offsetWidth;'
        '        if (outgoing) {'
        '            wrap.style.minHeight = outgoing.offsetHeight + "px";'
        '            animateOut(outgoing, w, incoming ? function() { animateIn(incoming, w, wrap); } : function() { wrap.style.minHeight = ""; });'
        '        } else {'
        '            animateIn(incoming, w, wrap);'
        '        }'
        '    }'
        '    var countEl = document.getElementById("lookup-count");'
        '    tabs.forEach(function(tab) {'
        '        tab.addEventListener("click", function() {'
        '            tabs.forEach(function(t) { t.classList.remove("active"); });'
        '            this.classList.add("active");'
        '            var target = this.getAttribute("data-tab");'
        '            document.querySelectorAll(".lookup-panel").forEach(function(panel) {'
        '                panel.style.display = panel.id === "lookup-panel-" + target ? "" : "none";'
        '            });'
        '            switchMosaics(target);'
        '            if (countEl) { var ct = this.getAttribute("data-count-text"); if (ct) countEl.textContent = ct; }'
        '            if (window._applyTabPage) window._applyTabPage(target);'
        '            if (window._layoutMatchGrids) window._layoutMatchGrids();'
        '        });'
        '    });'
        '})();'
        '(function() {'
        '    var PAGE_SIZE = 50;'
        '    var pagTabs = document.querySelectorAll(".lookup-tab");'
        '    if (!pagTabs.length) return;'
        '    var pagEl = document.getElementById("lookup-pagination");'
        '    var prevBtn = document.getElementById("pag-prev");'
        '    var nextBtn = document.getElementById("pag-next");'
        '    var labelEl = document.getElementById("pag-label");'
        '    var sizeBtn = document.getElementById("pag-size-btn");'
        '    var sizeMenu = document.getElementById("pag-size-menu");'
        '    var sizeValEl = document.getElementById("pag-size-val");'
        '    var sizeOpts = sizeMenu ? Array.from(sizeMenu.querySelectorAll(".pag-select-opt")) : [];'
        '    var state = {};'
        '    function getGrid(tabName) {'
        '        var panel = document.getElementById("lookup-panel-" + tabName);'
        '        return panel ? panel.querySelector(".match-grid") : null;'
        '    }'
        '    pagTabs.forEach(function(tab) {'
        '        var name = tab.getAttribute("data-tab");'
        '        var grid = getGrid(name);'
        '        var backCard = grid ? grid.querySelector(".match-card--back") : null;'
        '        var cards = grid ? Array.from(grid.querySelectorAll(".match-card:not(.match-card--back)")) : [];'
        '        var total = Math.max(1, Math.ceil(cards.length / PAGE_SIZE));'
        '        state[name] = { page: 1, total: total, cards: cards, backCard: backCard, ready: false };'
        '    });'
        '    function syncControls(tabName) {'
        '        if (!pagEl || !labelEl) return;'
        '        var s = state[tabName];'
        '        if (!s) return;'
        '        pagEl.style.visibility = "";'
        '        labelEl.textContent = s.page + " / " + s.total;'
        '        prevBtn.disabled = s.page <= 1;'
        '        nextBtn.disabled = s.page >= s.total;'
        '    }'
        '    function applyPage(tabName, page) {'
        '        var s = state[tabName];'
        '        if (!s) return;'
        '        s.page = page;'
        '        s.ready = true;'
        '        var grid = getGrid(tabName);'
        '        if (!grid) return;'
        '        var start = (page - 1) * PAGE_SIZE;'
        '        var pageCards = s.cards.slice(start, start + PAGE_SIZE);'
        '        grid.innerHTML = "";'
        '        if (s.backCard) grid.appendChild(s.backCard);'
        '        pageCards.forEach(function(c) { grid.appendChild(c); });'
        '    }'
        '    window._applyTabPage = function(tabName) {'
        '        var s = state[tabName];'
        '        if (!s) return;'
        '        if (!s.ready) applyPage(tabName, 1);'
        '        syncControls(tabName);'
        '    };'
        '    var initTab = document.querySelector(".lookup-tab.active");'
        '    if (initTab) {'
        '        var initName = initTab.getAttribute("data-tab");'
        '        applyPage(initName, 1);'
        '        syncControls(initName);'
        '        if (window._layoutMatchGrids) window._layoutMatchGrids();'
        '    }'
        '    function getActiveTab() {'
        '        var a = document.querySelector(".lookup-tab.active");'
        '        return a ? a.getAttribute("data-tab") : null;'
        '    }'
        '    if (prevBtn) prevBtn.addEventListener("click", function() {'
        '        var name = getActiveTab();'
        '        var s = state[name];'
        '        if (s && s.page > 1) {'
        '            applyPage(name, s.page - 1);'
        '            syncControls(name);'
        '            if (window._layoutMatchGrids) window._layoutMatchGrids();'
        '        }'
        '    });'
        '    if (nextBtn) nextBtn.addEventListener("click", function() {'
        '        var name = getActiveTab();'
        '        var s = state[name];'
        '        if (s && s.page < s.total) {'
        '            applyPage(name, s.page + 1);'
        '            syncControls(name);'
        '            if (window._layoutMatchGrids) window._layoutMatchGrids();'
        '        }'
        '    });'
        '    function applySize(value) {'
        '        PAGE_SIZE = value;'
        '        if (sizeValEl) sizeValEl.textContent = value;'
        '        sizeOpts.forEach(function(o) {'
        '            o.classList.toggle("pag-select-opt--active", parseInt(o.getAttribute("data-value"), 10) === value);'
        '        });'
        '        if (sizeMenu) sizeMenu.style.display = "none";'
        '        var activeName = getActiveTab();'
        '        for (var n in state) {'
        '            state[n].total = Math.max(1, Math.ceil(state[n].cards.length / PAGE_SIZE));'
        '            state[n].page = 1;'
        '            if (n !== activeName) state[n].ready = false;'
        '        }'
        '        if (activeName) {'
        '            applyPage(activeName, 1);'
        '            syncControls(activeName);'
        '            if (window._layoutMatchGrids) window._layoutMatchGrids();'
        '        }'
        '    }'
        '    if (sizeBtn) sizeBtn.addEventListener("click", function(e) {'
        '        e.stopPropagation();'
        '        if (sizeMenu) sizeMenu.style.display = sizeMenu.style.display === "block" ? "none" : "block";'
        '    });'
        '    sizeOpts.forEach(function(opt) {'
        '        opt.addEventListener("click", function() {'
        '            applySize(parseInt(this.getAttribute("data-value"), 10));'
        '        });'
        '    });'
        '    document.addEventListener("click", function(e) {'
        '        if (sizeMenu && sizeMenu.style.display === "block") {'
        '            var wrap = document.getElementById("pag-size-wrap");'
        '            if (wrap && !wrap.contains(e.target)) sizeMenu.style.display = "none";'
        '        }'
        '    });'
        '})();'
        '(function() {'
        '    var btn = document.getElementById("pag-expand-btn");'
        '    if (!btn) return;'
        '    btn.addEventListener("click", function() {'
        '        var on = this.classList.toggle("active");'
        '        document.querySelectorAll(".match-grid").forEach(function(g) {'
        '            g.classList.toggle("match-grid--expanded", on);'
        '        });'
        '    });'
        '})();'
        '(function() {'
        '    if (window.location.pathname === "/") {'
        '        sessionStorage.removeItem("art-tab");'
        '        return;'
        '    }'
        '    var art = document.querySelector(".sidebar-art");'
        '    if (!art) return;'
        '    var activeLink = document.querySelector(".sidebar a.active");'
        '    var currentTab = activeLink ? activeLink.getAttribute("href") : "";'
        '    var prevTab = sessionStorage.getItem("art-tab");'
        '    var artAnimating = prevTab !== currentTab;'
        '    if (artAnimating) {'
        '        var sidebar = document.querySelector(".sidebar");'
        '        sidebar.style.overflow = "hidden";'
        '        art.style.transform = "translateY(150px)";'
        '        art.style.opacity = "0";'
        '        requestAnimationFrame(function() {'
        '            requestAnimationFrame(function() {'
        '                art.style.transition = "transform 0.55s cubic-bezier(0.4,0,0.2,1), opacity 0.4s ease";'
        '                art.style.transform = "";'
        '                art.style.opacity = "";'
        '                art.addEventListener("transitionend", function cleanup(e) {'
        '                    if (e.propertyName !== "transform") return;'
        '                    art.style.transition = "";'
        '                    sidebar.style.overflow = "";'
        '                    art.removeEventListener("transitionend", cleanup);'
        '                });'
        '            });'
        '        });'
        '        sessionStorage.setItem("art-tab", currentTab);'
        '    }'
        '    var platter = document.querySelector(".sidebar-platter");'
        '    if (!platter) return;'
        '    platter.style.transform = "translateY(150px)";'
        '    platter.style.opacity = "0";'
        '    setTimeout(function() {'
        '        requestAnimationFrame(function() {'
        '            requestAnimationFrame(function() {'
        '                platter.style.transition = "transform 0.5s cubic-bezier(0.4,0,0.2,1), opacity 0.4s ease";'
        '                platter.style.transform = "translateY(0)";'
        '                platter.style.opacity = "1";'
        '                platter.addEventListener("transitionend", function onDone(e) {'
        '                    if (e.propertyName !== "transform") return;'
        '                    platter.style.transition = "";'
        '                    platter.style.transform = "";'
        '                    platter.style.opacity = "";'
        '                    platter.classList.add("spinning");'
        '                    platter.removeEventListener("transitionend", onDone);'
        '                });'
        '            });'
        '        });'
        '    }, artAnimating ? 600 : 200);'
        '})();'
        '</script>'
        '</body></html>'
    )

# Routes

## Landing Page ##

@app.route("/")
def landingpage():
    return page_layout(
        '<section class="hero">'
        '<div class="hero-eyebrow">Discogs Toolkit</div>'
        '<h1 class="hero-title">Tools for <em>crate diggers</em>, collectors, and sellers.</h1>'
        '<p class="hero-subtitle">A small set of utilities for marketplace research '
        'and collection matching for the Discogs platform. Dig through the shelves below.</p>'
        '<br><p class="hero-subtitle">\ Dev Notes \<br>'
        '01 &middot; Price Checker doesn\'t work when running on the cloud/web because webscraping gets blocked by Cloudflare. Works locally.<br>'
        '02 &middot; All good.<br>'
        '03 &middot; Displaying user lists doesn\'t work for the same issue with webscraping and Cloudflare.<br>'
        '( Report bugs to @curefortheitch on Instagram, Discogs, etc. )</p>'
        '</section>'
        '<div class="tool-grid-wrap">'
        '<div class="tool-grid">'
        '<a href="/pricechecker" class="tool-card">'
        '<div class="tool-card-label">01 &middot; Marketplace</div>'
        '<h3 class="tool-card-title">Price Checker</h3>'
        '<p class="tool-card-desc">See where a seller\'s listings rank against the rest of the marketplace.</p>'
        '</a>'
        '<a href="/matcher" class="tool-card">'
        '<div class="tool-card-label">02 &middot; Collections</div>'
        '<h3 class="tool-card-title">Collection Matcher</h3>'
        '<p class="tool-card-desc">Find overlap between one user\'s collection and another user\'s wantlist.</p>'
        '</a>'
        '<a href="/lookup" class="tool-card">'
        '<div class="tool-card-label">03 &middot; Collections</div>'
        '<h3 class="tool-card-title">User Lookup</h3>'
        '<p class="tool-card-desc">Browse any user\'s full collection and wantlist as well as any lists they have made.</p>'
        '</a>'
        '<div class="tool-slot"></div>'
        '<div class="tool-slot"></div>'
        '<div class="tool-slot"></div>'
        '<div class="tool-slot"></div>'
        '<div class="tool-slot"></div>'
        '<div class="tool-slot"></div>'
        '</div>'
        '</div>'
    )

## Price Checker Module ##

@app.route("/pricechecker")
def pricecheckerpage():

    seller = request.args.get("seller", "")
    output,loadtime = "",""
    show_platter = False
    inventory_count = 0

    if seller != "":
        start_time = time.time()
        try:
            sorted_inventory_list = [ [] for _ in range(10) ]

            print("Loading inventory...")

            scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})
            release_titles_ids = pricechecker.get_inventory_ids(seller, scraper)
            inventory_count = len(release_titles_ids)
            inventory_list = [None] * inventory_count

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(pricechecker.get_listings, scraper, inventory_list,
                                    sorted_inventory_list, seller, release[0], release[1], release[2], i)
                    for i, release in enumerate(release_titles_ids)
                ]
                for f in as_completed(futures):
                    f.result()

            mosaic = pricechecker.print_mosaic(inventory_list)
            if request.args.get("sort","") == "yes":
                results = mosaic + pricechecker.print_sorted_list(sorted_inventory_list)
            else:
                results = mosaic + pricechecker.print_list(inventory_list)
            output = '<div id="results-area"><div id="results-main">' + results + '</div></div>'
            show_platter = True

        except AttributeError:
            output = "No user found."

        end_time = time.time()
        seller_meta = "Seller: " + seller
        loadtime = "Search time: {0} seconds".format(round(end_time-start_time,2))
        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")

    inv_noun = "release" if inventory_count == 1 else "releases"
    meta = '<div class="meta"><span><b>{0}</b> &nbsp;&middot;&nbsp; {1} {2}</span><span>{3} &nbsp;&#124;&nbsp; {4}</span></div>'.format(seller_meta, inventory_count, inv_noun, loadtime, searched_at) if loadtime else ""

    seller_val = seller.replace('"', '&quot;')
    sort_checked = ' checked' if request.args.get("sort","") == "yes" else ''

    pc_header = (
        '<div class="page-header">'
        '<div class="page-eyebrow">Marketplace</div>'
        '<h2>Price <em>Checker</em></h2>'
        '</div>'
    )
    pc_form = (
        '<form id="pc-form" class="search-bar" action="" method="get" role="search">'
        '<span class="search-bar-icon" aria-hidden="true">' + SEARCH_ICON_SVG + '</span>'
        '<div class="search-bar-segment">'
        '<label class="search-bar-label" for="seller">Seller</label>'
        '<input type="text" id="seller" name="seller" placeholder="Discogs username" '
        'autocomplete="off" value="' + seller_val + '">'
        '</div>'
        '<div class="search-bar-divider"></div>'
        '<label class="search-bar-toggle" for="sort">'
        '<input type="checkbox" id="sort" name="sort" value="yes"' + sort_checked + '>'
        '<span>Sort by place</span>'
        '</label>'
        '<button type="submit" class="search-bar-submit">Search</button>'
        '</form>'
        '<div id="spinner"><span id="spinner-icon"></span>Pulling listings&hellip;</div>'
    )
    return page_layout(
        (pc_form + pc_header + meta + output) if seller else (pc_header + pc_form),
        content_class='has-results' if seller else '',
        show_platter=show_platter,
        title='Price Checker'
    )

## Matcher Module ##

@app.route("/matcher")
def matcherpage():

    collection_user = request.args.get("collection", "")
    wantlist_user = request.args.get("wantlist", "")
    exact = request.args.get("exact", "") == "yes"
    output,loadtime = "",""

    if collection_user != "" and wantlist_user != "" :
        start_time = time.time()
        try:
            scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})

            collection = matcher.get_collection(collection_user, scraper)
            wantlist = matcher.get_wantlist(wantlist_user, scraper)

            lookup_field = "key" if exact else "easy_key"
            wantlist_set = {w["strict"] if exact else w["easy"] for w in wantlist}
            collection_by_key = {item[lookup_field]: item for item in collection}
            matches = sorted(
                [collection_by_key[k] for k in collection_by_key if k in wantlist_set],
                key=lambda x: x["artist"].lower()
            )

            mosaic_items = ""
            match_lines = ""
            for m in matches:
                fmt_parts = ", ".join(p for p in [m.get("format_descriptions", ""), m.get("format_text", "")] if p)
                fmt_suffix = " ({0})".format(_html.escape(fmt_parts)) if fmt_parts else ""
                match_lines += "<b>" + _html.escape(m["artist"]) + "</b>" + " - " + _html.escape(m["title"]) + " &nbsp;&middot" + "<i>" + fmt_suffix + "</i>" + "<br>"
                if m.get("thumb"):
                    mosaic_items += '<span class="mosaic-item"><img src="{0}" alt="" class="mosaic-thumb"></span>'.format(m["thumb"])
            mosaic = '<div id="matcher-mosaic" class="mosaic">{0}</div>'.format(mosaic_items) if mosaic_items else ""

            matches_count = len(matches)
            matches_count_text = "Matches ({0})".format(matches_count)

            summary = (
                '<div class="result-card">'
                '<div class="card-title card-title--label">Results</div>'
                '<div class="card-listings">'
                'Collection: <b>{1}</b> ({0} items)<br>'
                'Wantlist: <b>{3}</b> ({2} items)<br>'
                '<br><b>Matches: {4} items</b><br>'
                + ('<br>' + match_lines if match_lines else '') +
                '</div>'
                '</div>'
            ).format(len(collection), collection_user, len(wantlist), wantlist_user, matches_count)

            tabs_html = (
                '<div class="lookup-tabs-row">'
                '<div class="lookup-tabs">'
                '<button class="lookup-tab active" data-tab="matches" data-count-text="' + _html.escape(matches_count_text) + '">' + _html.escape(matches_count_text) + '</button>'
                '</div>'
                '<div class="lookup-pagination" id="lookup-pagination">'
                '<button class="pag-expand-btn" id="pag-expand-btn" type="button" title="Expand all cards">'
                '<span class="pag-eye pag-eye--closed">' + EYE_CLOSED_SVG + '</span>'
                '<span class="pag-eye pag-eye--open">' + EYE_OPEN_SVG + '</span>'
                '</button>'
                '<div class="pag-select" id="pag-size-wrap">'
                '<button class="pag-select-btn" id="pag-size-btn" type="button">'
                '<span id="pag-size-val">50</span>'
                '<span class="pag-select-caret">&#9662;</span>'
                '</button>'
                '<div class="pag-select-menu" id="pag-size-menu">'
                '<button class="pag-select-opt" type="button" data-value="10">10</button>'
                '<button class="pag-select-opt" type="button" data-value="25">25</button>'
                '<button class="pag-select-opt pag-select-opt--active" type="button" data-value="50">50</button>'
                '<button class="pag-select-opt" type="button" data-value="100">100</button>'
                '</div>'
                '</div>'
                '<div class="pag-divider"></div>'
                '<button class="pag-btn" id="pag-prev">&#8249;</button>'
                '<span class="pag-label" id="pag-label">1 / 1</span>'
                '<button class="pag-btn" id="pag-next">&#8250;</button>'
                '</div>'
                '</div>'
            )

            grid = _render_lookup_grid(matches) if matches else '<p class="match-empty">No matches found.</p>'
            panel_html = '<div id="lookup-panel-matches" class="lookup-panel">' + grid + '</div>'

            output = mosaic + summary + tabs_html + panel_html

        except matcher.RateLimitError:
            output = _RATE_LIMIT_NOTICE
        except AttributeError:
            output = "Unable to find a match."

        end_time = time.time()
        loadtime = "Match time: {0} seconds".format(round(end_time-start_time,2))
        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")
        collection_meta = "Collection: " + collection_user
        wantlist_meta = "Wantlist: " + wantlist_user

    meta = '<div class="meta"><span><b>{0}</b> &nbsp;&middot;&nbsp; <b>{1}</b></span><span>{2} &nbsp;&#124;&nbsp; {3}</span></div>'.format(collection_meta, wantlist_meta, loadtime, searched_at) if loadtime else ""

    collection_val = collection_user.replace('"', '&quot;')
    wantlist_val = wantlist_user.replace('"', '&quot;')
    exact_checked = ' checked' if exact else ''

    has_results = collection_user != "" and wantlist_user != ""
    matcher_header = (
        '<div class="page-header">'
        '<div class="page-eyebrow">Collections</div>'
        '<h2>Collection <em>Matcher</em></h2>'
        '</div>'
    )
    matcher_form = (
        '<form id="matcher-form" class="search-bar" action="" method="get" role="search">'
        '<span class="search-bar-icon" aria-hidden="true">' + SEARCH_ICON_SVG + '</span>'
        '<div class="search-bar-segment">'
        '<label class="search-bar-label" for="collection">Collection</label>'
        '<input type="text" id="collection" name="collection" placeholder="username" '
        'autocomplete="off" value="' + collection_val + '">'
        '</div>'
        '<div class="search-bar-divider"></div>'
        '<div class="search-bar-segment">'
        '<label class="search-bar-label" for="wantlist">Wantlist</label>'
        '<input type="text" id="wantlist" name="wantlist" placeholder="username" '
        'autocomplete="off" value="' + wantlist_val + '">'
        '</div>'
        '<div class="search-bar-divider"></div>'
        '<label class="search-bar-toggle" for="exact">'
        '<input type="checkbox" id="exact" name="exact" value="yes"' + exact_checked + '>'
        '<span>Exact match</span>'
        '</label>'
        '<button type="submit" class="search-bar-submit">Search</button>'
        '</form>'
        '<div id="spinner"><span id="spinner-icon"></span>Matching&hellip;</div>'
    )
    return page_layout(
        (matcher_form + matcher_header + meta + output) if has_results else (matcher_header + matcher_form),
        content_class='has-results' if has_results else '',
        show_platter=has_results,
        title='Collection Matcher'
    )

## Lookup Module ##

def _render_lookup_grid(items, show_stats=False, prepend_card=""):
    cards = prepend_card
    for m in items:
        img_src = m.get("cover_image") or m.get("thumb")
        if img_src:
            art = '<img src="{0}" alt="" class="match-card-img">'.format(img_src)
        else:
            art = '<div class="match-card-placeholder">' + VINYL_PLACEHOLDER_SVG + '</div>'
        fmt_desc_html = ('<div class="match-card-format-desc">' + _html.escape(m.get("format_descriptions", "")) + '</div>') if m.get("format_descriptions") else ""
        fmt_text_html = ('<div class="match-card-format-text">' + _html.escape(m.get("format_text", "")) + '</div>') if m.get("format_text") else ""
        comment_html = ('<div class="match-card-comment">' + _html.escape(m.get("comment", "")) + '</div>') if m.get("comment") else ""
        stats_html = ('<div class="match-card-stats">' + _html.escape(m.get("stats", "")) + '</div>') if show_stats and m.get("stats") else ""
        for_sale_text = m.get("for_sale", "")
        for_sale_url = m.get("for_sale_url", "")
        for_sale_html = (
            '<div class="match-card-forsale" data-href="' + _html.escape(for_sale_url) + '"'
            ' onclick="event.stopPropagation();event.preventDefault();window.open(this.dataset.href,\'_blank\',\'noopener,noreferrer\')">'
            + _html.escape(for_sale_text) + '</div>'
        ) if for_sale_text and for_sale_url else ""
        href = m.get("url") or "#"
        cards += (
            '<a href="' + href + '" class="match-card" target="_blank" rel="noopener noreferrer">'
            '<div class="match-card-art">' + art + '</div>'
            '<div class="match-card-body">'
            '<div class="match-card-title">' + _html.escape(m.get("title", "")) + '</div>'
            '<div class="match-card-artist">' + _html.escape(m.get("artist", "")) + '</div>'
            + ('<div class="match-card-format">' + _html.escape(m.get("format", "")) + '</div>' if m.get("format") else "")
            + fmt_desc_html
            + fmt_text_html
            + for_sale_html
            + comment_html
            + stats_html +
            '</div>'
            '</a>'
        )
    return '<div class="match-grid">' + cards + '</div>'


def _render_list_index(lists, username):
    if not lists:
        return '<p class="match-empty">This user has no public lists.</p>'
    cards = ""
    for lst in lists:
        href = '/lookup?username=' + _html.escape(username) + '&list_id=' + _html.escape(str(lst["id"]))
        description_html = ('<div class="match-card-comment">' + _html.escape(lst["description"]) + '</div>') if lst.get("description") else ""
        cards += (
            '<a href="' + href + '" class="match-card">'
            '<div class="match-card-art">'
            '<div class="match-card-placeholder">' + VINYL_PLACEHOLDER_SVG + '</div>'
            '<div class="match-card-art-label">' + _html.escape(lst["name"]) + '</div>'
            '</div>'
            '<div class="match-card-body">'
            '<div class="match-card-title">' + _html.escape(lst["name"]) + '</div>'
            + description_html +
            '</div>'
            '</a>'
        )
    return '<div class="match-grid">' + cards + '</div>'


@app.route("/lookup")
def lookuppage():

    username = request.args.get("username", "")
    list_id = request.args.get("list_id", "")
    output, loadtime, searched_at, user_meta, active_count_text = "", "", "", "", ""
    has_results = bool(username)

    if username:
        start_time = time.time()
        scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})

        collection = None
        wantlist = None
        lists = None
        list_releases = None
        user_not_found = False
        rate_limited = False
        collection_error = ""
        wantlist_error = ""
        lists_error = ""

        try:
            try:
                collection = lookup_helper.get_collection(username, scraper)
            except lookup_helper.UserNotFoundError:
                user_not_found = True
            except lookup_helper.CollectionPrivateError:
                collection_error = "This user's collection is not public."

            if not user_not_found:
                try:
                    wantlist = lookup_helper.get_wantlist(username, scraper)
                except lookup_helper.UserNotFoundError:
                    user_not_found = True
                except lookup_helper.WantlistPrivateError:
                    wantlist_error = "This user's wantlist is not public."

            if not user_not_found:
                try:
                    lists = lookup_helper.get_lists(username, scraper)
                except lookup_helper.UserNotFoundError:
                    user_not_found = True
                except lookup_helper.ListPrivateError:
                    lists_error = "This user's lists are not public."

            if list_id and not user_not_found:
                list_releases = lookup_helper.get_list_releases(list_id, scraper)

        except lookup_helper.RateLimitError:
            rate_limited = True

        end_time = time.time()
        loadtime = "Lookup time: {0} seconds".format(round(end_time - start_time, 2))
        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")
        user_meta = "User: " + username

        if rate_limited:
            output = _RATE_LIMIT_NOTICE
        elif user_not_found:
            output = (
                '<div class="lookup-notice lookup-notice--error">'
                'User <b>' + _html.escape(username) + '</b> was not found on Discogs. '
                'Check the username and try again.'
                '</div>'
            )
        else:
            col_count = len(collection) if collection is not None else 0
            want_count = len(wantlist) if wantlist is not None else 0
            lists_count = len(lists) if lists is not None else 0
            active_tab = "lists" if list_id else "collection"

            def _count_text(n, noun):
                return "{0} {1}{2}".format(n, noun, "" if n == 1 else "s")

            col_count_text   = _count_text(col_count, "item")
            want_count_text  = _count_text(want_count, "item")
            if list_id:
                list_rel_count = len(list_releases) if list_releases else 0
                lists_count_text = _count_text(list_rel_count, "release")
            else:
                lists_count_text = _count_text(lists_count, "list")
            active_count_text = {"collection": col_count_text, "wantlist": want_count_text, "lists": lists_count_text}[active_tab]

            tabs_html = (
                '<div class="lookup-tabs-row">'
                '<div class="lookup-tabs">'
                '<button class="lookup-tab{0}" data-tab="collection" data-count-text="{5}">Collection ({1})</button>'
                '<button class="lookup-tab" data-tab="wantlist" data-count-text="{6}">Wantlist ({2})</button>'
                '<button class="lookup-tab{3}" data-tab="lists" data-count-text="{7}">Lists ({4})</button>'
                '</div>'
                '<div class="lookup-pagination" id="lookup-pagination">'
                '<button class="pag-expand-btn" id="pag-expand-btn" type="button" title="Expand all cards">'
                '<span class="pag-eye pag-eye--closed">' + EYE_CLOSED_SVG + '</span>'
                '<span class="pag-eye pag-eye--open">' + EYE_OPEN_SVG + '</span>'
                '</button>'
                '<div class="pag-select" id="pag-size-wrap">'
                '<button class="pag-select-btn" id="pag-size-btn" type="button">'
                '<span id="pag-size-val">50</span>'
                '<span class="pag-select-caret">&#9662;</span>'
                '</button>'
                '<div class="pag-select-menu" id="pag-size-menu">'
                '<button class="pag-select-opt" type="button" data-value="10">10</button>'
                '<button class="pag-select-opt" type="button" data-value="25">25</button>'
                '<button class="pag-select-opt pag-select-opt--active" type="button" data-value="50">50</button>'
                '<button class="pag-select-opt" type="button" data-value="100">100</button>'
                '</div>'
                '</div>'
                '<div class="pag-divider"></div>'
                '<button class="pag-btn" id="pag-prev">&#8249;</button>'
                '<span class="pag-label" id="pag-label">1 / 1</span>'
                '<button class="pag-btn" id="pag-next">&#8250;</button>'
                '</div>'
                '</div>'
            ).format(
                ' active' if active_tab == 'collection' else '',
                col_count,
                want_count,
                ' active' if active_tab == 'lists' else '',
                lists_count,
                _html.escape(col_count_text),
                _html.escape(want_count_text),
                _html.escape(lists_count_text),
            )

            if collection_error:
                col_content = '<div class="lookup-notice">' + _html.escape(collection_error) + '</div>'
            elif collection:
                col_content = _render_lookup_grid(collection, show_stats=False)
            else:
                col_content = '<p class="match-empty">This collection is empty.</p>'

            if wantlist_error:
                want_content = '<div class="lookup-notice">' + _html.escape(wantlist_error) + '</div>'
            elif wantlist:
                want_content = _render_lookup_grid(wantlist, show_stats=True)
            else:
                want_content = '<p class="match-empty">This wantlist is empty.</p>'

            if list_id:
                back_url = '/lookup?username=' + _html.escape(username)
                back_card_html = (
                    '<a href="' + back_url + '" class="match-card match-card--back">'
                    '<div class="match-card-art">'
                    '<div class="match-card-placeholder">' + BACK_ARROW_SVG + '</div>'
                    '</div>'
                    '</a>'
                )
                if list_releases:
                    lists_content = _render_lookup_grid(list_releases, prepend_card=back_card_html)
                else:
                    lists_content = _render_lookup_grid([], prepend_card=back_card_html) + '<p class="match-empty">This list is empty.</p>'
            elif lists_error:
                lists_content = '<div class="lookup-notice">' + _html.escape(lists_error) + '</div>'
            else:
                lists_content = _render_list_index(lists or [], username)

            col_mosaic_items = "".join(
                '<a class="mosaic-item" href="{1}" target="_blank" rel="noopener noreferrer"><img src="{0}" alt="" class="mosaic-thumb"></a>'.format(m["thumb"], m.get("url", "#"))
                for m in (collection or []) if m.get("thumb")
            )
            want_mosaic_items = "".join(
                '<a class="mosaic-item" href="{1}" target="_blank" rel="noopener noreferrer"><img src="{0}" alt="" class="mosaic-thumb"></a>'.format(m["thumb"], m.get("url", "#"))
                for m in (wantlist or []) if m.get("thumb")
            )
            lists_mosaic_items = "".join(
                '<span class="mosaic-item"><img src="{0}" alt="" class="mosaic-thumb"></span>'.format(m["thumb"])
                for m in (list_releases or []) if m.get("thumb")
            ) if list_id else ""

            col_hidden = ' style="display:none"' if active_tab != 'collection' else ''
            want_hidden = ' style="display:none"'
            lists_hidden = ' style="display:none"' if active_tab != 'lists' else ''

            col_mosaic = '<div id="lookup-mosaic-collection" class="lookup-mosaic mosaic"{1}>{0}</div>'.format(col_mosaic_items, col_hidden) if col_mosaic_items else ""
            want_mosaic = '<div id="lookup-mosaic-wantlist" class="lookup-mosaic mosaic"{1}>{0}</div>'.format(want_mosaic_items, want_hidden) if want_mosaic_items else ""
            lists_mosaic = '<div id="lookup-mosaic-lists" class="lookup-mosaic mosaic"{1}>{0}</div>'.format(lists_mosaic_items, lists_hidden) if lists_mosaic_items else ""
            mosaics_html = '<div class="lookup-mosaic-wrap">' + col_mosaic + want_mosaic + lists_mosaic + '</div>' if (col_mosaic or want_mosaic or lists_mosaic) else ""

            output = (
                mosaics_html +
                tabs_html +
                '<div id="lookup-panel-collection" class="lookup-panel"{0}>'.format(col_hidden) + col_content + '</div>' +
                '<div id="lookup-panel-wantlist" class="lookup-panel"{0}>'.format(want_hidden) + want_content + '</div>' +
                '<div id="lookup-panel-lists" class="lookup-panel"{0}>'.format(lists_hidden) + lists_content + '</div>'
            )

    count_span = ' &nbsp;&middot;&nbsp; <span id="lookup-count">{0}</span>'.format(_html.escape(active_count_text)) if active_count_text else ''
    meta = '<div class="meta"><span><b>{0}</b>{1}</span><span>{2} &nbsp;&#124;&nbsp; {3}</span></div>'.format(user_meta, count_span, loadtime, searched_at) if loadtime else ""

    username_val = username.replace('"', '&quot;')

    lookup_header = (
        '<div class="page-header">'
        '<div class="page-eyebrow">Collections</div>'
        '<h2>User <em>Lookup</em></h2>'
        '</div>'
    )
    lookup_form = (
        '<form id="lookup-form" class="search-bar" action="" method="get" role="search">'
        '<span class="search-bar-icon" aria-hidden="true">' + SEARCH_ICON_SVG + '</span>'
        '<div class="search-bar-segment">'
        '<label class="search-bar-label" for="username">Username</label>'
        '<input type="text" id="username" name="username" placeholder="Discogs username" '
        'autocomplete="off" value="' + username_val + '">'
        '</div>'
        '<button type="submit" class="search-bar-submit">Search</button>'
        '</form>'
        '<div id="spinner"><span id="spinner-icon"></span>Looking up user&hellip;</div>'
    )
    return page_layout(
        (lookup_form + lookup_header + meta + output) if has_results else (lookup_header + lookup_form),
        content_class='has-results' if has_results else '',
        show_platter=has_results,
        title='User Lookup'
    )


## Local Testing ##

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True, threaded=True)
