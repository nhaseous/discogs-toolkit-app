(function() {
    function parseDateKey(str) {
        if (!str) return 0;
        var parts = str.split(/[\/\-\.]/);
        if (parts.length !== 3) return 0;
        var a = parseInt(parts[0], 10), b = parseInt(parts[1], 10), c = parseInt(parts[2], 10);
        if (parts[0].length === 4) return a * 10000 + b * 100 + c;
        var y = c < 100 ? c + 2000 : c;
        return y * 10000 + a * 100 + b;
    }

    var panels = { collection: null, inventory: null, sold: null };
    ['collection','inventory','sold'].forEach(function(id) {
        panels[id] = document.getElementById('rec-panel-' + id);
    });

    var dashGroups = {};
    document.querySelectorAll('.rec-dash-group').forEach(function(g) {
        dashGroups[g.dataset.tabGroup] = g;
    });

    var breakdownPanes = {};
    document.querySelectorAll('.rec-breakdown-pane').forEach(function(p) {
        breakdownPanes[p.dataset.breakdownPane] = p;
    });

    var TAB_TO_GROUP = { collection: 'col-inv', inventory: 'col-inv', sold: 'sold' };

    function switchBreakdownPane(target) {
        var current = null;
        Object.keys(breakdownPanes).forEach(function(k) {
            if (breakdownPanes[k].style.display !== 'none') current = breakdownPanes[k];
        });
        var next = breakdownPanes[target];
        if (!next || next === current) return;

        if (current) {
            current.classList.add('rec-dash-leaving');
            setTimeout(function() {
                current.style.display = 'none';
                current.classList.remove('rec-dash-leaving');
            }, 180);
        }

        next.style.cssText = '';
        next.classList.add('rec-dash-entering');
        void next.offsetWidth;
        next.classList.remove('rec-dash-entering');
    }

    function switchDashGroup(target) {
        var groupKey = TAB_TO_GROUP[target] || target;
        var currentGroup = null;
        Object.keys(dashGroups).forEach(function(k) {
            if (dashGroups[k].style.display !== 'none') currentGroup = dashGroups[k];
        });
        var nextGroup = dashGroups[groupKey];

        if (breakdownPanes[target] !== undefined) {
            if (currentGroup === nextGroup) {
                switchBreakdownPane(target);
            } else {
                Object.keys(breakdownPanes).forEach(function(k) {
                    breakdownPanes[k].style.cssText = k === target ? '' : 'display:none;opacity:0';
                });
            }
        }

        if (!nextGroup || nextGroup === currentGroup) return;

        if (currentGroup) {
            currentGroup.classList.add('rec-dash-leaving');
            setTimeout(function() {
                currentGroup.style.display = 'none';
                currentGroup.classList.remove('rec-dash-leaving');
            }, 180);
        }

        nextGroup.style.cssText = '';
        nextGroup.classList.add('rec-dash-entering');
        void nextGroup.offsetWidth;
        nextGroup.classList.remove('rec-dash-entering');
    }

    document.querySelectorAll('.rec-tab').forEach(function(tab) {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.rec-tab').forEach(function(t) { t.classList.remove('active'); });
            this.classList.add('active');
            var target = this.dataset.tab;
            Object.keys(panels).forEach(function(id) {
                panels[id].style.display = id === target ? '' : 'none';
            });
            switchDashGroup(target);
        });
    });

    ['collection','inventory','sold'].forEach(function(folder) {
        var panel = panels[folder];
        if (!panel) return;

        var table    = panel.querySelector('.rec-table');
        var tbody    = table ? table.querySelector('tbody') : null;
        var searchEl = panel.querySelector('.rec-search');
        var countEl  = panel.querySelector('.rec-count');
        var sfTabsEl = panel.querySelector('.rec-sf-tabs');

        if (!tbody) return;

        var currentSF  = '__all__';
        var sortCol    = null;
        var sortDir    = 1;
        var originalOrder = Array.from(tbody.querySelectorAll('tr'));

        function allRows()    { return Array.from(tbody.querySelectorAll('tr')); }
        function recordRows() { return Array.from(tbody.querySelectorAll('tr:not(.rec-sf-header)')); }
        function sfHeaders()  { return Array.from(tbody.querySelectorAll('tr.rec-sf-header')); }

        function applyFilters() {
            var q  = searchEl ? searchEl.value.toLowerCase().trim() : '';
            var sf = currentSF;

            recordRows().forEach(function(row) {
                var matchSF     = sf === '__all__' || row.dataset.sf === sf;
                var matchSearch = !q ||
                    (row.dataset.artist || '').includes(q) ||
                    (row.dataset.album  || '').includes(q);
                row.style.display = matchSF && matchSearch ? '' : 'none';
            });

            sfHeaders().forEach(function(hdr) {
                if (sortCol) { hdr.style.display = 'none'; return; }
                var hSF = hdr.dataset.sf;
                if (sf !== '__all__' && hSF !== sf) { hdr.style.display = 'none'; return; }
                var hasVisible = recordRows().some(function(r) {
                    return r.dataset.sf === hSF && r.style.display !== 'none';
                });
                hdr.style.display = hasVisible ? '' : 'none';
            });

            if (countEl) {
                var n = recordRows().filter(function(r) { return r.style.display !== 'none'; }).length;
                countEl.textContent = n + ' record' + (n === 1 ? '' : 's');
            }
        }

        function sortTable(col, dir) {
            var recs = recordRows();
            var numeric = ['cost','median','total','sold-for'].indexOf(col) !== -1;
            var isDate  = ['acquired','date'].indexOf(col) !== -1;
            recs.sort(function(a, b) {
                if (isDate)  return dir * (parseDateKey(a.dataset[col]) - parseDateKey(b.dataset[col]));
                var av = numeric ? (parseFloat(a.dataset[col]) || 0) : (a.dataset[col] || '');
                var bv = numeric ? (parseFloat(b.dataset[col]) || 0) : (b.dataset[col] || '');
                if (numeric) return dir * (av - bv);
                return dir * av.localeCompare(bv);
            });
            recs.forEach(function(r) { tbody.appendChild(r); });
            applyFilters();
        }

        function resetSort() {
            originalOrder.forEach(function(r) { tbody.appendChild(r); });
            sortCol = null; sortDir = 1;
            panel.querySelectorAll('th.sortable').forEach(function(th) {
                th.classList.remove('sort-asc','sort-desc');
            });
            applyFilters();
        }

        panel.querySelectorAll('th.sortable').forEach(function(th) {
            th.addEventListener('click', function() {
                var col = this.dataset.col;
                if (sortCol === col) {
                    if (sortDir === -1) { resetSort(); return; }
                    sortDir = -1;
                } else {
                    sortCol = col; sortDir = 1;
                }
                panel.querySelectorAll('th.sortable').forEach(function(t) {
                    t.classList.remove('sort-asc','sort-desc');
                });
                this.classList.add(sortDir === 1 ? 'sort-asc' : 'sort-desc');
                sortTable(sortCol, sortDir);
            });
        });

        if (searchEl) {
            searchEl.addEventListener('input', applyFilters);
        }

        if (sfTabsEl) {
            sfTabsEl.querySelectorAll('.rec-sf-tab').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    sfTabsEl.querySelectorAll('.rec-sf-tab').forEach(function(b) { b.classList.remove('active'); });
                    this.classList.add('active');
                    currentSF = this.dataset.sf;
                    if (sortCol) resetSort();
                    applyFilters();
                });
            });
        }

        applyFilters();
    });
})();
