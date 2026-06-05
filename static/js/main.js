// ==========================================================
// main.js — global UI on every page: sidebar nav, badge tooltip,
// search-form submit animation, sidebar art/platter (PDF export),
// and pywebview external-link handling.
// Shared card-grid logic lives in grid.js; Lookup browsing in
// lookup-browse.js.
// ==========================================================

(function() {
    var toggle = document.getElementById('sidebar-toggle');
    if (!toggle) return;
    var KEY = 'sidebar-collapsed';
    function apply(collapsed) {
        document.documentElement.classList.toggle('sidebar-collapsed', collapsed);
    }
    toggle.addEventListener('click', function() {
        var next = !document.documentElement.classList.contains('sidebar-collapsed');
        apply(next);
        localStorage.setItem(KEY, next ? '1' : '0');
    });
})();

document.querySelectorAll(".sidebar a").forEach(function(link) {
    link.addEventListener("click", function(e) {
        if (this.pathname === window.location.pathname) {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: "smooth" });
            history.replaceState(null, "", window.location.pathname + window.location.search);
        }
    });
});

(function() {
    var tip = document.getElementById("badge-tooltip");
    if (!tip) return;
    document.querySelectorAll(".inv-count-badge[data-tooltip]").forEach(function(badge) {
        badge.addEventListener("mouseenter", function(e) {
            var s = window.getComputedStyle(this);
            tip.textContent = this.getAttribute("data-tooltip");
            tip.style.background = s.backgroundColor;
            tip.style.color = s.color;
            tip.style.left = e.clientX + "px";
            tip.style.top = e.clientY + "px";
            tip.style.display = "block";
        });
        badge.addEventListener("mousemove", function(e) {
            tip.style.left = e.clientX + "px";
            tip.style.top = e.clientY + "px";
        });
        badge.addEventListener("mouseleave", function() {
            tip.style.display = "none";
        });
    });
})();

(function() {
    function attachFormAnim(formId) {
        var form = document.getElementById(formId);
        if (!form) return;
        form.addEventListener("submit", function(e) {
            e.preventDefault();
            form.nextElementSibling.style.display = "block";
            var header = document.querySelector(".page-header");
            if (header) {
                var formRect = form.getBoundingClientRect();
                var gap = parseInt(window.getComputedStyle(form).marginBottom) || 22;
                var targetTop = 30;
                var delta = targetTop - formRect.top;
                if (delta < 0) {
                    var headerShift = (targetTop + formRect.height + gap) - header.getBoundingClientRect().top;
                    var ease = "transform 0.4s cubic-bezier(0.4,0,0.2,1)";
                    form.style.transition = ease;
                    form.style.transform = "translateY(" + delta + "px)";
                    header.style.transition = ease;
                    header.style.transform = "translateY(" + headerShift + "px)";
                    form.addEventListener("transitionend", function() { form.submit(); }, { once: true });
                    return;
                }
            }
            requestAnimationFrame(function() { requestAnimationFrame(function() { form.submit(); }); });
        });
    }
    attachFormAnim("pc-form");
    attachFormAnim("matcher-form");
    attachFormAnim("lookup-form");
    attachFormAnim("recommend-form");
})();

(function() {
    if (window.location.pathname === "/") {
        sessionStorage.removeItem("art-tab");
        return;
    }
    var art = document.querySelector(".sidebar-art");
    if (!art) return;
    var activeLink = document.querySelector(".sidebar a.active");
    var currentTab = activeLink ? activeLink.getAttribute("href") : "";
    var prevTab = sessionStorage.getItem("art-tab");
    var artAnimating = prevTab !== currentTab;
    if (artAnimating) {
        var sidebar = document.querySelector(".sidebar");
        sidebar.style.overflow = "hidden";
        art.style.transform = "translateY(150px)";
        art.style.opacity = "0";
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                art.style.transition = "transform 0.55s cubic-bezier(0.4,0,0.2,1), opacity 0.4s ease";
                art.style.transform = "";
                art.style.opacity = "";
                art.addEventListener("transitionend", function cleanup(e) {
                    if (e.propertyName !== "transform") return;
                    art.style.transition = "";
                    sidebar.style.overflow = "";
                    art.removeEventListener("transitionend", cleanup);
                });
            });
        });
        sessionStorage.setItem("art-tab", currentTab);
    }
    var platter = document.querySelector(".sidebar-platter");
    if (!platter) return;

    platter.setAttribute("title", "Export page as PDF");
    platter.setAttribute("role", "button");
    platter.setAttribute("aria-label", "Export page as PDF");
    platter.addEventListener("click", function() {
        var path = window.location.pathname;
        var qs = new URLSearchParams(window.location.search);
        var pageNames = {
            "/": "Home",
            "/pricechecker": "Price Checker",
            "/matcher": "Matcher",
            "/lookup": "Lookup",
            "/records": "Records"
        };
        var parts = ["Discogs Toolkit", pageNames[path] || path.replace(/^\//, "") || "Page"];
        if (path === "/pricechecker" && qs.get("seller")) parts.push(qs.get("seller"));
        else if (path === "/matcher" && (qs.get("collection") || qs.get("wantlist"))) {
            parts.push((qs.get("collection") || "?") + " + " + (qs.get("wantlist") || "?"));
        }
        else if (path === "/lookup" && qs.get("username")) {
            var u = qs.get("username");
            if (qs.get("list_id")) u += " list " + qs.get("list_id");
            parts.push(u);
        }
        var originalTitle = document.title;
        document.title = parts.join(" - ");
        var restore = function() {
            document.title = originalTitle;
            window.removeEventListener("afterprint", restore);
        };
        window.addEventListener("afterprint", restore);
        window.print();
    });

    platter.style.transform = "translateY(150px)";
    platter.style.opacity = "0";
    setTimeout(function() {
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                platter.style.transition = "transform 0.5s cubic-bezier(0.4,0,0.2,1), opacity 0.4s ease";
                platter.style.transform = "translateY(0)";
                platter.style.opacity = "1";
                platter.addEventListener("transitionend", function onDone(e) {
                    if (e.propertyName !== "transform") return;
                    platter.style.transition = "";
                    platter.style.transform = "";
                    platter.style.opacity = "";
                    platter.classList.add("spinning");
                    platter.removeEventListener("transitionend", onDone);
                });
            });
        });
    }, artAnimating ? 600 : 200);
})();

// External link handling for pywebview (MacOS App)
(function() {
    function getExternalUrl(el) {
        if (!el) return null;
        var href = el.getAttribute('href') || el.dataset.href;
        if (!href) return null;
        
        // Check if it's a relative URL or points to the same host
        var a = document.createElement('a');
        a.href = href;
        if (a.hostname && a.hostname !== window.location.hostname && a.hostname !== 'localhost') {
            return a.href;
        }
        return null;
    }

    function openExternal(url) {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.open_external) {
            window.pywebview.api.open_external(url);
            return true;
        }
        return false;
    }

    document.addEventListener('click', function(e) {
        var el = e.target.closest('a, [data-href]');
        if (!el) return;

        var url = getExternalUrl(el);
        if (url && openExternal(url)) {
            e.preventDefault();
            e.stopPropagation();
        }
    }, true);

    // Intercept window.open
    var originalOpen = window.open;
    window.open = function(url, target, features) {
        if (url) {
            var a = document.createElement('a');
            a.href = url;
            if (a.hostname && a.hostname !== window.location.hostname && a.hostname !== 'localhost') {
                if (openExternal(a.href)) {
                    return null;
                }
            }
        }
        return originalOpen(url, target, features);
    };
})();
