from flask import Flask, request, send_from_directory
from helper import pricechecker, matcher
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
    '<circle cx="50" cy="50" r="20" fill="#1a1208"/>'
    '<circle cx="50" cy="50" r="4" fill="currentColor"/>'
    '</svg>'
)

SEARCH_ICON_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>'
)

def page_layout(content, content_class=""):
    path = request.path
    pc_active = ' class="active"' if path == '/pricechecker' else ''
    matcher_active = ' class="active"' if path == '/matcher' else ''
    return (
        '<!DOCTYPE html>'
        '<html lang="en">'
        '<head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Discogs Toolkit</title>'
        '<link rel="icon" type="image/png" sizes="64x64" href="/static/favicon.png">'
        '<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;1,9..144,400;1,9..144,500'
        '&family=Inter:wght@400;500;600;700&display=swap">'
        '<link rel="stylesheet" href="/static/style.css">'
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
        '    function revealMosaic() {'
        '        mosaic.style.transition = "none";'
        '        mosaic.style.opacity = "0";'
        '        container.classList.remove("sticky-mosaic-active");'
        '        var contentMain = document.getElementById("content-main");'
        '        var mosaicRect = mosaic.getBoundingClientRect();'
        '        var contentRect = contentMain ? contentMain.getBoundingClientRect() : mosaicRect;'
        '        var startX = contentRect.left - mosaicRect.left;'
        '        mosaic.style.transform = "translateX(" + startX + "px)";'
        '        requestAnimationFrame(function() {'
        '            requestAnimationFrame(function() {'
        '                mosaic.style.transition = "transform 0.35s cubic-bezier(0.4,0,0.2,1), opacity 0.35s ease";'
        '                mosaic.style.transform = "translateX(0)";'
        '                mosaic.style.opacity = "1";'
        '                mosaic.addEventListener("transitionend", function cleanup() {'
        '                    mosaic.style.transition = "";'
        '                    mosaic.style.transform = "";'
        '                    mosaic.style.opacity = "";'
        '                    mosaic.removeEventListener("transitionend", cleanup);'
        '                });'
        '            });'
        '        });'
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
        '})();'
        '</script>'
        '</body></html>'
    )

# Routes

@app.route('/favicon.ico')
def favicon_ico():
    return send_from_directory(app.static_folder, 'favicon.png', mimetype='image/png')

## Landing Page ##

@app.route("/")
def landingpage():
    return page_layout(
        '<section class="hero">'
        '<div class="hero-eyebrow">Discogs Toolkit</div>'
        '<h1 class="hero-title">Tools for <em>crate diggers</em>, collectors, and sellers.</h1>'
        '<p class="hero-subtitle">A small set of utilities for Discogs marketplace research '
        'and collection matching. Dig through the shelves below.</p>'
        '</section>'
        '<div class="tool-grid">'
        '<a href="/pricechecker" class="tool-card">'
        '<div class="tool-card-label">01 &middot; Marketplace</div>'
        '<h3 class="tool-card-title">Price Checker</h3>'
        '<p class="tool-card-desc">See where a seller\'s listings rank against the rest of the marketplace.</p>'
        '</a>'
        '<a href="/matcher" class="tool-card">'
        '<div class="tool-card-label">02 &middot; Collections</div>'
        '<h3 class="tool-card-title">Matcher</h3>'
        '<p class="tool-card-desc">Find overlap between one user\'s collection and another user\'s wantlist.</p>'
        '</a>'
        '</div>'
    )

## Price Checker Module ##

@app.route("/pricechecker")
def pricecheckerpage():

    seller = request.args.get("seller", "")
    output,loadtime = "",""

    if seller != "":
        start_time = time.time()
        try:
            sorted_inventory_list = [ [] for _ in range(10) ]

            print("Loading inventory...")

            scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})
            release_titles_ids = pricechecker.get_inventory_ids(seller, scraper)
            inventory_list = [None] * len(release_titles_ids)

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

        except AttributeError:
            output = "No user found."

        end_time = time.time()
        seller_meta = "Seller: " + seller
        loadtime = "Search time: {0} seconds".format(round(end_time-start_time,2))
        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")

    meta = '<div class="meta"><span><b>{0}</b> &nbsp;&middot;&nbsp; {1}</span><span>{2}</span></div>'.format(seller_meta, loadtime, searched_at) if loadtime else ""

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
        content_class='has-results' if seller else ''
    )

## Matcher Module ##

@app.route("/matcher")
def matcherpage():

    collection_user = request.args.get("collection", "")
    wantlist_user = request.args.get("wantlist", "")
    output,loadtime = "",""

    start_time = time.time()
    if collection_user != "" and wantlist_user != "" :
        try:
            scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})

            collection = matcher.get_collection(collection_user, scraper)
            wantlist = matcher.get_wantlist(wantlist_user, scraper)

            collection_by_key = {item["key"]: item for item in collection}
            wantlist_set = set(wantlist)
            matches = sorted(
                [collection_by_key[k] for k in collection_by_key if k in wantlist_set],
                key=lambda x: x["artist"].lower()
            )

            match_lines = ""
            for m in matches:
                fmt_parts = ", ".join(p for p in [m.get("format_descriptions", ""), m.get("format_text", "")] if p)
                fmt_suffix = " ({0})".format(_html.escape(fmt_parts)) if fmt_parts else ""
                match_lines += _html.escape(m["artist"]) + " - " + _html.escape(m["title"]) + fmt_suffix + "<br>"

            mosaic_items = ""
            for m in matches:
                if m.get("thumb"):
                    mosaic_items += '<span class="mosaic-item"><img src="{0}" alt="" class="mosaic-thumb"></span>'.format(m["thumb"])
            mosaic = '<div id="matcher-mosaic" class="mosaic">{0}</div>'.format(mosaic_items) if mosaic_items else ""

            summary = (
                '<div class="result-card">'
                '<div class="card-title card-title--label">Results</div>'
                '<div class="card-listings">'
                'Collection: <b>{1}</b> ({0} items)<br>'
                'Wantlist: <b>{3}</b> ({2} items)<br>'
                + ('<br>' + match_lines if match_lines else '') +
                '<br><b>Matches: {4} items</b>'
                '</div>'
                '</div>'
            ).format(len(collection), collection_user, len(wantlist), wantlist_user, len(matches))

            if matches:
                cards = ""
                for m in matches:
                    if m["thumb"]:
                        art = '<img src="{0}" alt="" class="match-card-img">'.format(m["thumb"])
                    else:
                        art = '<div class="match-card-placeholder">' + VINYL_PLACEHOLDER_SVG + '</div>'
                    fmt_desc_html = ('<div class="match-card-format-desc">' + _html.escape(m["format_descriptions"]) + '</div>') if m.get("format_descriptions") else ""
                    fmt_text_html = ('<div class="match-card-format-text">' + _html.escape(m["format_text"]) + '</div>') if m.get("format_text") else ""
                    cards += (
                        '<a href="' + m["url"] + '" class="match-card" target="_blank" rel="noopener noreferrer">'
                        '<div class="match-card-art">' + art + '</div>'
                        '<div class="match-card-body">'
                        '<div class="match-card-title">' + _html.escape(m["title"]) + '</div>'
                        '<div class="match-card-artist">' + _html.escape(m["artist"]) + '</div>'
                        '<div class="match-card-format">' + _html.escape(m["format"]) + '</div>'
                        + fmt_desc_html +
                        fmt_text_html +
                        '</div>'
                        '</a>'
                    )
                grid = '<div class="match-grid">' + cards + '</div>'
            else:
                grid = '<p class="match-empty">No matches found.</p>'

            output = mosaic + summary + grid

        except AttributeError:
            output = "Unable to find a match."

        end_time = time.time()
        loadtime = "Load time: {0} seconds".format(round(end_time-start_time,2))
        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")
        collection_meta = "Collection: " + collection_user
        wantlist_meta = "Wantlist: " + wantlist_user

    meta = '<div class="meta"><span><b>{0}</b> &nbsp;&middot;&nbsp; <b>{1}</b> &nbsp;&middot;&nbsp; {2}</span><span>{3}</span></div>'.format(collection_meta, wantlist_meta, loadtime, searched_at) if loadtime else ""

    collection_val = collection_user.replace('"', '&quot;')
    wantlist_val = wantlist_user.replace('"', '&quot;')

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
        '<button type="submit" class="search-bar-submit">Search</button>'
        '</form>'
        '<div id="spinner"><span id="spinner-icon"></span>Matching&hellip;</div>'
    )
    return page_layout(
        (matcher_form + matcher_header + meta + output) if has_results else (matcher_header + matcher_form),
        content_class='has-results' if has_results else ''
    )

## Testing Page ##

@app.route("/test")
def testingpage():
    # server = server.PriceCheckerServer(user1, webhook1)
    # server.serve()
    return page_layout(
        """
        <input type="text" name="wantlist">
        testing
        """
    )

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
