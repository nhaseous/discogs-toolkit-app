/**
 * static/js/utils.js
 * Shared utility functions for DOM manipulation, scrolling, and formatting.
 */

window.ToolkitUtils = {
    /**
     * Scroll to a target element (like a tabs row) after executing an action.
     * Guards page height to prevent layout shifts.
     */
    withScrollGuard: function(action, targetSelector) {
        var targetEl = document.querySelector(targetSelector);
        var contentMain = document.getElementById("content-main");
        var currentY = window.pageYOffset;

        if (contentMain) {
            contentMain.style.minHeight = (currentY + window.innerHeight) + "px";
        }
        
        if (action) action();

        if (targetEl) {
            var oldPos = targetEl.style.position;
            targetEl.style.position = "static";
            
            var targetY = 0;
            var curr = targetEl;
            while (curr && curr !== document.body) {
                targetY += curr.offsetTop;
                curr = curr.offsetParent;
            }
            
            targetEl.style.position = oldPos;
            window.scrollTo({ top: targetY, behavior: "smooth" });
        }

        setTimeout(function() {
            if (contentMain) contentMain.style.minHeight = "";
        }, 600);
    },

    /**
     * Returns the ordinal suffix for a number (1st, 2nd, etc.)
     */
    ordinal: function(n) {
        if (11 <= (n % 100) && (n % 100) <= 13) return n + "th";
        return n + ({1: "st", 2: "nd", 3: "rd"}[n % 10] || "th");
    },

    /**
     * Shared badge counting logic used by Price Checker and Reprice tools.
     */
    updateBadgeCounts: function(containerSelector, badgeSelector) {
        var container = document.querySelector(containerSelector) || document;
        var badgeContainer = document.querySelector(badgeSelector);
        if (!badgeContainer) return;

        var counts = {
            recent: 0, old: 0, lowest: 0, low: 0, high: 0, highest: 0,
            cheapest: 0, overpriced: 0, watch: 0
        };

        container.querySelectorAll(".result-card").forEach(function(card) {
            var badges = (card.getAttribute("data-badges") || "").split(" ");
            badges.forEach(function(b) { if (counts.hasOwnProperty(b)) counts[b]++; });
        });

        badgeContainer.querySelectorAll(".inv-count-badge").forEach(function(badge) {
            var key = badge.getAttribute("data-filter");
            if (counts.hasOwnProperty(key)) {
                var ct = badge.nextElementSibling;
                if (ct && ct.classList.contains("badge-ct")) {
                    ct.textContent = counts[key];
                }
            }
        });
    }
};
