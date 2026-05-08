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
    var active = new Set();
    var pills = document.querySelectorAll(".inv-count-badge[data-filter]");
    if (!pills.length) return;
    pills.forEach(function(pill) {
        pill.addEventListener("click", function() {
            var f = this.getAttribute("data-filter");
            if (active.has(f)) {
                active.delete(f);
                this.classList.remove("filter-active");
                if (f === "low") {
                    active.delete("lowest");
                    var lb = document.querySelector(".inv-count-badge[data-filter='lowest']");
                    if (lb) lb.classList.remove("filter-active");
                }
            } else {
                active.add(f);
                this.classList.add("filter-active");
                if (f === "lowest") {
                    active.add("low");
                    var lowb = document.querySelector(".inv-count-badge[data-filter='low']");
                    if (lowb) lowb.classList.add("filter-active");
                }
                if (f === "recent") {
                    active.delete("old");
                    var oldb = document.querySelector(".inv-count-badge[data-filter='old']");
                    if (oldb) oldb.classList.remove("filter-active");
                }
                if (f === "old") {
                    active.delete("recent");
                    var recentb = document.querySelector(".inv-count-badge[data-filter='recent']");
                    if (recentb) recentb.classList.remove("filter-active");
                }
            }
            filter();
        });
    });
    function filter() {
        document.querySelectorAll(".result-card").forEach(function(card) {
            if (!active.size) { card.style.display = ""; return; }
            var cb = (card.getAttribute("data-badges") || "").split(" ");
            var show = true;
            active.forEach(function(f) { if (cb.indexOf(f) === -1) show = false; });
            card.style.display = show ? "" : "none";
        });
        document.querySelectorAll(".sort-group-header").forEach(function(hdr) {
            if (!active.size) { hdr.style.display = ""; return; }
            var sib = hdr.nextElementSibling;
            var vis = false;
            while (sib && !sib.classList.contains("sort-group-header")) {
                if (sib.classList.contains("result-card") && sib.style.display !== "none") { vis = true; break; }
                sib = sib.nextElementSibling;
            }
            hdr.style.display = vis ? "" : "none";
        });
    }
})();

(function() {
    var mosaic = document.getElementById("results-mosaic");
    if (!mosaic) return;
    var container = mosaic.closest(".content");
    var sticky = null;
    var syncObservers = [];
    function reposition() {
        if (!sticky) return;
        sticky.style.left = document.getElementById("content-main").getBoundingClientRect().right + 48 + "px";
    }
    function activate() {
        if (sticky) return;
        sticky = document.createElement("div");
        sticky.id = "sticky-mosaic";
        mosaic.querySelectorAll(".mosaic-item").forEach(function(item) {
            sticky.appendChild(item.cloneNode(true));
        });
        var invCount = mosaic.nextElementSibling;
        if (invCount) {
            var cloned = invCount.cloneNode(true);
            cloned.querySelectorAll(".inv-count-badge[data-filter]").forEach(function(cb) {
                cb.addEventListener("click", function(e) {
                    e.stopPropagation();
                    var orig = invCount.querySelector(".inv-count-badge[data-filter='" + this.getAttribute("data-filter") + "']");
                    if (orig) orig.click();
                });
            });
            invCount.querySelectorAll(".inv-count-badge[data-filter]").forEach(function(ob) {
                var mo = new MutationObserver(function() {
                    var cb = cloned.querySelector(".inv-count-badge[data-filter='" + ob.getAttribute("data-filter") + "']");
                    if (cb) cb.classList.toggle("filter-active", ob.classList.contains("filter-active"));
                });
                mo.observe(ob, { attributes: true, attributeFilter: ["class"] });
                syncObservers.push(mo);
            });
            var origRC = invCount.querySelector(".reprice-controls");
            var cloneRC = cloned.querySelector(".reprice-controls");
            if (origRC && cloneRC) {
                var origBtns = origRC.querySelectorAll("button");
                var cloneBtns = cloneRC.querySelectorAll("button");
                cloneBtns.forEach(function(cloneBtn, idx) {
                    var origBtn = origBtns[idx];
                    if (!origBtn) return;
                    cloneBtn.addEventListener("click", function(e) {
                        e.stopPropagation();
                        origBtn.click();
                    });
                    var moBtn = new MutationObserver(function() {
                        cloneBtn.style.cssText = origBtn.style.cssText;
                        cloneBtn.className = origBtn.className;
                        if (cloneBtn.textContent !== origBtn.textContent) cloneBtn.textContent = origBtn.textContent;
                    });
                    moBtn.observe(origBtn, { attributes: true, attributeFilter: ["style", "class"], childList: true, characterData: true, subtree: true });
                    syncObservers.push(moBtn);
                });
                var moRC = new MutationObserver(function() {
                    cloneRC.style.cssText = origRC.style.cssText;
                });
                moRC.observe(origRC, { attributes: true, attributeFilter: ["style"] });
                syncObservers.push(moRC);
                var origStatus = origRC.querySelector(".reprice-status");
                var cloneStatus = cloneRC.querySelector(".reprice-status");
                if (origStatus && cloneStatus) {
                    var moSt = new MutationObserver(function() {
                        cloneStatus.style.cssText = origStatus.style.cssText;
                        cloneStatus.textContent = origStatus.textContent;
                    });
                    moSt.observe(origStatus, { attributes: true, attributeFilter: ["style"], childList: true, characterData: true, subtree: true });
                    syncObservers.push(moSt);
                }
            }
            sticky.appendChild(cloned);
        }
        document.body.appendChild(sticky);
        reposition();
        window.addEventListener("resize", reposition);
        container.classList.add("sticky-mosaic-active");
        sticky.style.transform = "translateY(-100%)";
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                if (!sticky) return;
                sticky.style.transition = "transform 0.35s cubic-bezier(0.4,0,0.2,1)";
                sticky.style.transform = "translateY(0)";
            });
        });
    }
    var MOSAIC_EASE = "transform 0.35s cubic-bezier(0.4,0,0.2,1), opacity 0.28s ease";
    function slideInMosaic() {
        var w = mosaic.offsetWidth;
        var clip = document.getElementById("content-main");
        if (clip) clip.style.overflow = "hidden";
        mosaic.style.transition = "none";
        mosaic.style.transform = "translateX(-" + w + "px)";
        mosaic.style.opacity = "0";
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                mosaic.style.transition = MOSAIC_EASE;
                mosaic.style.transform = "translateX(0)";
                mosaic.style.opacity = "1";
                mosaic.addEventListener("transitionend", function cleanup(e) {
                    if (e.propertyName !== "transform") return;
                    mosaic.removeEventListener("transitionend", cleanup);
                    mosaic.style.transition = "";
                    mosaic.style.transform = "";
                    mosaic.style.opacity = "";
                    if (clip) clip.style.overflow = "";
                });
            });
        });
    }
    function revealMosaic() {
        container.classList.remove("sticky-mosaic-active");
        slideInMosaic();
    }
    function deactivate() {
        if (!sticky) return;
        syncObservers.forEach(function(mo) { mo.disconnect(); });
        syncObservers = [];
        window.removeEventListener("resize", reposition);
        var el = sticky;
        sticky = null;
        el.style.transition = "transform 0.35s cubic-bezier(0.4,0,0.2,1)";
        el.style.transform = "translateY(-100%)";
        el.addEventListener("transitionend", function() { el.remove(); revealMosaic(); }, { once: true });
    }
    new IntersectionObserver(function(entries) {
        if (!entries[0].isIntersecting && entries[0].boundingClientRect.top < 0) { activate(); }
    }).observe(mosaic);
    var invCount = mosaic.nextElementSibling;
    if (invCount) {
        new IntersectionObserver(function(entries) {
            if (!entries[0].isIntersecting) return;
            if (sticky) { deactivate(); return; }
            if (!container.classList.contains("sticky-mosaic-active")) return;
            revealMosaic();
        }).observe(invCount);
    }
    slideInMosaic();
})();

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
})();

(function() {
    function layoutMatchGrid(grid) {
        var allCards = Array.from(grid.querySelectorAll(".match-card"));
        if (!allCards.length) return;
        var gap = 14, minWidth = 158;
        var numCols = Math.max(1, Math.floor((grid.offsetWidth + gap) / (minWidth + gap)));
        var existing = Array.from(grid.children);
        if (existing.length === numCols && existing.every(function(c) { return c.classList.contains("match-column"); })) return;
        grid.innerHTML = "";
        var cols = [];
        for (var i = 0; i < numCols; i++) {
            var col = document.createElement("div");
            col.className = "match-column";
            grid.appendChild(col);
            cols.push(col);
        }
        allCards.forEach(function(c, i) { cols[i % numCols].appendChild(c); });
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

(function() {
    var tabs = document.querySelectorAll(".lookup-tab");
    if (!tabs.length) return;
    var EASE = "transform 0.35s cubic-bezier(0.4,0,0.2,1), opacity 0.28s ease";
    function animateOut(el, w, onDone) {
        el.style.transition = EASE;
        el.style.transform = "translateX(-" + w + "px)";
        el.style.opacity = "0";
        el.addEventListener("transitionend", function cleanup(e) {
            if (e.propertyName !== "transform") return;
            el.removeEventListener("transitionend", cleanup);
            el.style.display = "none";
            el.style.transition = ""; el.style.transform = ""; el.style.opacity = "";
            if (onDone) onDone();
        });
    }
    function animateIn(el, w, wrap) {
        el.style.transition = "none";
        el.style.transform = "translateX(-" + w + "px)";
        el.style.opacity = "0";
        el.style.display = "";
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                el.style.transition = EASE;
                el.style.transform = "translateX(0)";
                el.style.opacity = "1";
                el.addEventListener("transitionend", function done(e) {
                    if (e.propertyName !== "transform") return;
                    el.removeEventListener("transitionend", done);
                    el.style.transition = ""; el.style.transform = ""; el.style.opacity = "";
                    if (wrap) wrap.style.minHeight = "";
                });
            });
        });
    }
    function switchMosaics(target) {
        var all = Array.from(document.querySelectorAll(".lookup-mosaic"));
        var incoming = document.getElementById("lookup-mosaic-" + target);
        var outgoing = all.find(function(m) { return m !== incoming && m.style.display !== "none"; });
        if (!incoming && !outgoing) return;
        var wrap = (outgoing || incoming).parentNode;
        var w = wrap.offsetWidth;
        if (outgoing) {
            wrap.style.minHeight = outgoing.offsetHeight + "px";
            animateOut(outgoing, w, incoming ? function() { animateIn(incoming, w, wrap); } : function() { wrap.style.minHeight = ""; });
        } else {
            animateIn(incoming, w, wrap);
        }
    }
    var countEl = document.getElementById("lookup-count");
    tabs.forEach(function(tab) {
        tab.addEventListener("click", function() {
            tabs.forEach(function(t) { t.classList.remove("active"); });
            this.classList.add("active");
            var target = this.getAttribute("data-tab");
            document.querySelectorAll(".lookup-panel").forEach(function(panel) {
                panel.style.display = panel.id === "lookup-panel-" + target ? "" : "none";
            });
            switchMosaics(target);
            if (countEl) { var ct = this.getAttribute("data-count-text"); if (ct) countEl.textContent = ct; }
            if (window._resetMatchCardHover) window._resetMatchCardHover();
            if (window._applyTabPage) window._applyTabPage(target);
            if (window._layoutMatchGrids) window._layoutMatchGrids();
        });
    });
})();

(function() {
    var PAGE_SIZE = 50;
    var pagTabs = document.querySelectorAll(".lookup-tab");
    if (!pagTabs.length) return;
    var pagEl = document.getElementById("lookup-pagination");
    var prevBtn = document.getElementById("pag-prev");
    var nextBtn = document.getElementById("pag-next");
    var labelEl = document.getElementById("pag-label");
    var sizeBtn = document.getElementById("pag-size-btn");
    var sizeMenu = document.getElementById("pag-size-menu");
    var sizeValEl = document.getElementById("pag-size-val");
    var sizeOpts = sizeMenu ? Array.from(sizeMenu.querySelectorAll(".pag-select-opt")) : [];
    var state = {};
    function getGrid(tabName) {
        var panel = document.getElementById("lookup-panel-" + tabName);
        return panel ? panel.querySelector(".match-grid") : null;
    }
    pagTabs.forEach(function(tab) {
        var name = tab.getAttribute("data-tab");
        var grid = getGrid(name);
        var backCard = grid ? grid.querySelector(".match-card--back") : null;
        var cards = grid ? Array.from(grid.querySelectorAll(".match-card:not(.match-card--back)")) : [];
        var total = Math.max(1, Math.ceil(cards.length / PAGE_SIZE));
        state[name] = { page: 1, total: total, cards: cards, backCard: backCard, ready: false };
    });
    function syncControls(tabName) {
        if (!pagEl || !labelEl) return;
        var s = state[tabName];
        if (!s) return;
        pagEl.style.visibility = "";
        labelEl.textContent = s.page + " / " + s.total;
        prevBtn.disabled = s.page <= 1;
        nextBtn.disabled = s.page >= s.total;
    }
    function applyPage(tabName, page) {
        var s = state[tabName];
        if (!s) return;
        s.page = page;
        s.ready = true;
        var grid = getGrid(tabName);
        if (!grid) return;
        var start = (page - 1) * PAGE_SIZE;
        var pageCards = s.cards.slice(start, start + PAGE_SIZE);
        grid.innerHTML = "";
        if (s.backCard) grid.appendChild(s.backCard);
        pageCards.forEach(function(c) { grid.appendChild(c); });
    }
    window._applyTabPage = function(tabName) {
        var s = state[tabName];
        if (!s) return;
        if (!s.ready) applyPage(tabName, 1);
        syncControls(tabName);
    };
    var initTab = document.querySelector(".lookup-tab.active");
    if (initTab) {
        var initName = initTab.getAttribute("data-tab");
        applyPage(initName, 1);
        syncControls(initName);
        if (window._layoutMatchGrids) window._layoutMatchGrids();
    }
    function getActiveTab() {
        var a = document.querySelector(".lookup-tab.active");
        return a ? a.getAttribute("data-tab") : null;
    }
    if (prevBtn) prevBtn.addEventListener("click", function() {
        var name = getActiveTab();
        var s = state[name];
        if (s && s.page > 1) {
            applyPage(name, s.page - 1);
            syncControls(name);
            if (window._layoutMatchGrids) window._layoutMatchGrids();
        }
    });
    if (nextBtn) nextBtn.addEventListener("click", function() {
        var name = getActiveTab();
        var s = state[name];
        if (s && s.page < s.total) {
            applyPage(name, s.page + 1);
            syncControls(name);
            if (window._layoutMatchGrids) window._layoutMatchGrids();
        }
    });
    function applySize(value) {
        PAGE_SIZE = value;
        if (sizeValEl) sizeValEl.textContent = value;
        sizeOpts.forEach(function(o) {
            o.classList.toggle("pag-select-opt--active", parseInt(o.getAttribute("data-value"), 10) === value);
        });
        if (sizeMenu) sizeMenu.style.display = "none";
        var activeName = getActiveTab();
        for (var n in state) {
            state[n].total = Math.max(1, Math.ceil(state[n].cards.length / PAGE_SIZE));
            state[n].page = 1;
            if (n !== activeName) state[n].ready = false;
        }
        if (activeName) {
            applyPage(activeName, 1);
            syncControls(activeName);
            if (window._layoutMatchGrids) window._layoutMatchGrids();
        }
    }
    if (sizeBtn) sizeBtn.addEventListener("click", function(e) {
        e.stopPropagation();
        if (sizeMenu) sizeMenu.style.display = sizeMenu.style.display === "block" ? "none" : "block";
    });
    sizeOpts.forEach(function(opt) {
        opt.addEventListener("click", function() {
            applySize(parseInt(this.getAttribute("data-value"), 10));
        });
    });
    document.addEventListener("click", function(e) {
        if (sizeMenu && sizeMenu.style.display === "block") {
            var wrap = document.getElementById("pag-size-wrap");
            if (wrap && !wrap.contains(e.target)) sizeMenu.style.display = "none";
        }
    });
})();

(function() {
    var btn = document.getElementById("pag-expand-btn");
    if (!btn) return;
    btn.addEventListener("click", function() {
        var on = this.classList.toggle("active");
        document.querySelectorAll(".match-grid").forEach(function(g) {
            g.classList.toggle("match-grid--expanded", on);
        });
    });
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
