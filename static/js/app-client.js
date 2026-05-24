/**
 * static/js/app-client.js
 * Consolidated client for application-specific API calls.
 * Includes centralized error handling for common application issues.
 */

window.ToolkitAPI = {
    /**
     * Internal helper to handle fetch responses and common errors.
     */
    _handleResponse: function(response) {
        if (response.status === 401) {
            // Optional: trigger a session timeout notification or redirect to login
            return response.json().then(function(data) {
                return Promise.reject({ status: 401, message: data.message || "Session expired. Please log in again." });
            });
        }
        if (response.status === 403) {
            return response.json().then(function(data) {
                return Promise.reject({ status: 403, message: data.message || "Access denied. Check your permissions." });
            });
        }
        if (!response.ok) {
            return response.json().then(function(data) {
                return Promise.reject({ status: response.status, message: data.message || "An unexpected error occurred." });
            }).catch(function() {
                return Promise.reject({ status: response.status, message: "Network error (HTTP " + response.status + ")" });
            });
        }
        return response.json();
    },

    /**
     * Fetches the watchlist for a specific seller.
     */
    getWatchlist: function(seller) {
        return fetch("/watchlist?seller=" + encodeURIComponent(seller))
            .then(this._handleResponse);
    },

    /**
     * Updates the watchlist for a specific seller.
     */
    postWatchlist: function(seller, watchlist) {
        return fetch("/watchlist", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({seller: seller, watchlist: watchlist})
        }).then(this._handleResponse);
    },

    /**
     * Requests a batch of marketplace scrapes for the given releases.
     */
    scrapeBatch: function(seller, releases, signal) {
        return fetch("/scrape_batch", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({seller: seller, releases: releases}),
            signal: signal
        }).then(this._handleResponse);
    },

    /**
     * Updates one or more listings for a seller.
     */
    reprice: function(seller, listings) {
        return fetch("/reprice", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({listings: listings, seller: seller})
        }).then(function(r) {
            // Reprice needs the raw response to check .ok and .status separately
            // due to how reprice.js handles partial success/auth errors.
            return r.json().then(function(data) { 
                return {ok: r.ok, status: r.status, data: data}; 
            });
        });
    },

    /**
     * Refreshes the display data (badges, place) for a single release card.
     */
    refreshCard: function(seller, releaseId, listingIds, title, thumbnail) {
        return fetch("/refresh_card", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                seller: seller, 
                release_id: releaseId, 
                listing_ids: listingIds,
                title: title,
                thumbnail: thumbnail
            })
        }).then(this._handleResponse);
    },

    /**
     * Loads a deferred tab's items and insights.
     */
    loadLookupTab: function(username, tabName) {
        var url = '/lookup/load-tab?username=' + encodeURIComponent(username) +
                  '&tab=' + encodeURIComponent(tabName);
        return fetch(url, { headers: { 'Accept': 'application/json' } })
            .then(this._handleResponse);
    },

    /**
     * Fetches the full data for a lookup tab (hydration).
     */
    getLookupData: function(username, tabName, listId) {
        var url = '/lookup/data?username=' + encodeURIComponent(username) +
                  '&tab=' + encodeURIComponent(tabName) +
                  (listId ? '&list_id=' + encodeURIComponent(listId) : '');
        return fetch(url, { headers: { 'Accept': 'application/json' } })
            .then(this._handleResponse);
    }
};
