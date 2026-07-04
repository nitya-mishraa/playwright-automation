/* ── Global Chart Defaults ─────────────────────────────────────────────── */
if (typeof Chart !== 'undefined') {
  Chart.defaults.color = '#6c7293';
  Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
  Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
  Chart.defaults.font.size = 12;
}

/* ── Sidebar Toggle (mobile) ───────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
  const toggleBtn = document.getElementById('sidebarToggle');
  const sidebar   = document.getElementById('appSidebar');
  const overlay   = document.getElementById('sidebarOverlay');

  function openSidebar()  { sidebar?.classList.add('open');  overlay?.classList.add('show'); }
  function closeSidebar() { sidebar?.classList.remove('open'); overlay?.classList.remove('show'); }

  toggleBtn?.addEventListener('click', () =>
    sidebar?.classList.contains('open') ? closeSidebar() : openSidebar()
  );
  overlay?.addEventListener('click', closeSidebar);

  // Keyword sidebar search
  const kwSearchInput = document.getElementById('kwSearch');
  if (kwSearchInput) {
    kwSearchInput.addEventListener('input', function() {
      const q = this.value.toLowerCase().trim();
      document.querySelectorAll('.kw-nav-item').forEach(function(item) {
        item.style.display = (!q || (item.dataset.kwname || '').includes(q)) ? '' : 'none';
      });
    });
  }
});

/* ── Live Table Search ─────────────────────────────────────────────────── */
const _searchListeners = {};

function initSearch(inputId, tableBodyId, countId) {
  const input   = document.getElementById(inputId);
  const tbody   = document.getElementById(tableBodyId);
  const countEl = countId ? document.getElementById(countId) : null;
  if (!input || !tbody) return;

  // Remove any previous listener so re-init after table rebuild doesn't stack
  if (_searchListeners[inputId]) {
    input.removeEventListener('input', _searchListeners[inputId]);
  }

  const handler = function () {
    const q        = this.value.toLowerCase().trim();
    const rows     = tbody.querySelectorAll('tr[data-searchable]');
    const emptyRow = tbody.querySelector('tr.empty-row');
    let visible = 0;
    rows.forEach(row => {
      const match = !q || row.textContent.toLowerCase().includes(q);
      row.style.display = match ? '' : 'none';
      if (match) visible++;
    });
    if (countEl) countEl.textContent = visible;
    if (emptyRow) emptyRow.style.display = visible === 0 ? '' : 'none';
  };

  _searchListeners[inputId] = handler;
  input.addEventListener('input', handler);

  const total = tbody.querySelectorAll('tr[data-searchable]').length;
  if (countEl) countEl.textContent = total;
}

/* ── Modal Population (generic) ────────────────────────────────────────── */
function setModalField(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  const v = (value !== null && value !== undefined && value !== '' && value !== '—' && value !== '-')
    ? String(value) : null;
  el.textContent = v || '—';
  el.style.color = v ? '' : 'var(--muted)';
}

function populateBidModal(bid) {
  if (!bid) return;
  const bd  = bid.detail?.bid_details   || {};
  const buy = bid.detail?.buyer_details  || {};
  const te  = bid.detail?.technical_evaluation || [];
  const fe  = bid.detail?.financial_evaluation || [];

  // Header
  setModalField('m-bid-no', bid.bid_no);

  const statusBadge = document.getElementById('m-status-badge');
  if (statusBadge) {
    statusBadge.textContent = bid.status || '';
    statusBadge.style.display = bid.status ? '' : 'none';
  }
  const catBadge = document.getElementById('m-category-badge');
  if (catBadge) {
    if (bid.category) {
      catBadge.textContent = bid.category.charAt(0).toUpperCase() + bid.category.slice(1);
      catBadge.className = 'tag tag-' + bid.category;
      catBadge.style.display = '';
    } else {
      catBadge.style.display = 'none';
    }
  }

  // Bid Details
  setModalField('m-bid-number',   bd.bid_number || bid.bid_no);
  setModalField('m-bid-status',   bd.bid_status);
  setModalField('m-bid-start',    bd.bid_start_datetime);
  setModalField('m-bid-end',      bd.bid_end_datetime);
  setModalField('m-bid-open',     bd.bid_opening_datetime);
  setModalField('m-bid-validity', bd.bid_validity_days ? bd.bid_validity_days + ' days' : '');
  setModalField('m-experience',   bd.experience_with_gov_required);

  // Buyer Details
  setModalField('m-buyer-name',   buy.name);
  setModalField('m-ministry',     buy.ministry);
  setModalField('m-department',   buy.department);
  setModalField('m-org',          buy.organisation);
  setModalField('m-office',       buy.office);
  setModalField('m-address',      buy.address);

  // Item
  setModalField('m-item', bid.items_full || bid.items_short || bid.items);

  // Listing source
  const listingWrap = document.getElementById('m-listing-wrap');
  if (listingWrap) listingWrap.style.display = bid.listing ? '' : 'none';
  setModalField('m-listing', bid.listing);

  // L1 Award
  const l1Price  = bid.l1_price && bid.l1_price !== 'N/A' ? bid.l1_price : '';
  const l1Seller = ((bid.l1_seller_full || bid.l1_seller || '').trim()).replace(/^—$/, '');
  setModalField('m-l1-price',  l1Price);
  setModalField('m-l1-seller', l1Seller);
  const l1Price_el = document.getElementById('m-l1-price');
  if (l1Price_el) l1Price_el.style.color = l1Price ? '#2dc653' : 'var(--muted)';

  // Count badges
  const techCount = document.getElementById('m-tech-count');
  if (techCount) techCount.textContent = te.length || '';
  const finCount = document.getElementById('m-fin-count');
  if (finCount) finCount.textContent = fe.length || '';

  // LLM Intelligence Section
  const llmSection = document.getElementById('m-llm-section');
  const scoreNum   = document.getElementById('m-score-num');
  const scoreCirc  = document.getElementById('m-score-circle');
  const scoreLabel = document.getElementById('m-score-label');
  const matchEl    = document.getElementById('m-matching-caps');
  const missEl     = document.getElementById('m-missing-caps');
  const recEl      = document.getElementById('m-recommendation');

  if (llmSection) {
    const score = (bid.relevance_score != null) ? parseInt(bid.relevance_score, 10) : null;
    if (score != null) {
      llmSection.style.display = '';
      // Colour coding
      const color = score >= 85 ? '#2dc653' : (score >= 70 ? '#4cc9f0' : (score >= 40 ? '#ffd60a' : '#f72585'));
      const label = score >= 85 ? 'Pursue'  : (score >= 70 ? 'Relevant' : (score >= 40 ? 'Consider' : 'Skip'));
      const deg   = Math.round(score * 3.6);  // 0–100 → 0–360deg

      if (scoreNum)  { scoreNum.textContent = score; scoreNum.style.color = color; }
      if (scoreLabel) { scoreLabel.textContent = label; scoreLabel.style.color = color; }
      if (scoreCirc) {
        scoreCirc.style.setProperty('--score-color', color);
        scoreCirc.style.setProperty('--score-deg', deg + 'deg');
        scoreCirc.style.background =
          `conic-gradient(${color} ${deg}deg, #1b1d30 0deg)`;
      }

      const caps = bid.matching_capabilities || [];
      if (matchEl) {
        matchEl.innerHTML = caps.length
          ? caps.map(c => `<li style="display:flex;align-items:flex-start;gap:5px"><i class="bi bi-check2" style="color:#2dc653;flex-shrink:0;margin-top:2px"></i><span>${_esc(c)}</span></li>`).join('')
          : '<li style="color:var(--muted)">None identified</li>';
      }

      const miss = bid.missing_capabilities || [];
      if (missEl) {
        missEl.innerHTML = miss.length
          ? miss.map(c => `<li style="display:flex;align-items:flex-start;gap:5px"><i class="bi bi-x" style="color:#f3722c;flex-shrink:0;margin-top:2px"></i><span>${_esc(c)}</span></li>`).join('')
          : '<li style="color:#2dc653"><i class="bi bi-check2-all me-1"></i>No gaps — full capability match</li>';
      }

      if (recEl) {
        recEl.textContent = bid.recommendation || '—';
        recEl.style.borderLeftColor = color;
      }
    } else {
      llmSection.style.display = 'none';
    }
  }

  // Technical Evaluation Table
  const tBody = document.getElementById('m-tech-tbody');
  if (tBody) {
    if (te.length) {
      tBody.innerHTML = te.map(r => `
        <tr>
          <td>${_esc(r.sr_no || '')}</td>
          <td>${_esc(r.seller_name || '—')}</td>
          <td style="max-width:160px;white-space:normal;word-break:break-word;font-size:0.76rem">${_esc(r.offered_item || '—')}</td>
          <td style="white-space:nowrap">${_esc(r.participated_on || '—')}</td>
          <td>${(r.mse_mii_status && r.mse_mii_status !== 'N/A' && r.mse_mii_status !== '—')
            ? '<span class="tag tag-mse" style="font-size:0.68rem">MSE/MII</span>'
            : '<span style="color:var(--muted)">—</span>'}</td>
          <td><span class="tag tag-qualified" style="font-size:0.68rem">${_esc(r.status || '—')}</span></td>
        </tr>`).join('');
    } else {
      tBody.innerHTML = '<tr><td colspan="6" class="text-center text-secondary py-3">No data</td></tr>';
    }
  }

  // Financial Evaluation Table
  const fBody = document.getElementById('m-fin-tbody');
  if (fBody) {
    if (fe.length) {
      fBody.innerHTML = fe.map(r => {
        const rankClass = ['L1','L2','L3'].includes(r.rank) ? 'rank-' + r.rank : 'rank-xx';
        const price = (r.total_price || '').replace('`', '₹');
        return `
        <tr>
          <td>${_esc(r.sr_no || '')}</td>
          <td>${_esc(r.seller_name || '—')}</td>
          <td style="max-width:160px;white-space:normal;word-break:break-word;font-size:0.76rem">${_esc(r.offered_item || '—')}</td>
          <td style="white-space:nowrap;color:${r.rank === 'L1' ? '#2dc653' : 'inherit'}">${_esc(price) || '—'}</td>
          <td><span class="rank-badge ${rankClass}">${_esc(r.rank || '—')}</span></td>
        </tr>`;
      }).join('');
    } else {
      fBody.innerHTML = '<tr><td colspan="5" class="text-center text-secondary py-3">No data</td></tr>';
    }
  }
}

/* ── Attach modal trigger ────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
  const modal = document.getElementById('bidModal');
  if (!modal) return;

  modal.addEventListener('show.bs.modal', function (e) {
    const btn = e.relatedTarget;
    const idx = parseInt(btn?.dataset.bidIdx, 10);
    if (isNaN(idx) || !window.BIDS_DATA) return;
    populateBidModal(window.BIDS_DATA[idx]);
  });
});

/* ── Keyword Filter ─────────────────────────────────────────────────────── */

function _esc(s) {
  return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ── Relevance bucket / filter bar (shared across all bid tables) ───────── */
function _relevanceBucket(score) {
  if (score == null) return 'none';
  const s = parseInt(score, 10);
  if (isNaN(s)) return 'none';
  if (s >= 85) return 'pursue';
  if (s >= 70) return 'relevant';
  if (s >= 40) return 'consider';
  return 'skip';
}

function _relevanceMatches(rowBucket, filterValue) {
  if (!filterValue) return true;
  return rowBucket === filterValue;
}

// Recomputes the count badges on a relevance_filter_bar() after its bid set changes.
function _updateRelevanceCounts(barId, bids) {
  const bar = document.getElementById(barId);
  if (!bar) return;
  const counts = { pursue: 0, relevant: 0, consider: 0, skip: 0 };
  (bids || []).forEach(function (b) {
    const bucket = _relevanceBucket(b.relevance_score != null ? b.relevance_score : null);
    if (counts[bucket] !== undefined) counts[bucket]++;
  });
  const totalEl = bar.querySelector('.rel-filter-btn[data-bucket=""] .rel-count');
  if (totalEl) totalEl.textContent = bids ? bids.length : 0;
  Object.keys(counts).forEach(function (k) {
    const el = bar.querySelector('.rel-filter-btn[data-bucket="' + k + '"] .rel-count');
    if (el) el.textContent = counts[k];
  });
}

// Wires a relevance_filter_bar()'s buttons; calls onChange(bucket) on every click.
function initRelevanceFilterBar(barId, onChange) {
  const bar = document.getElementById(barId);
  if (!bar) return;
  const btns = bar.querySelectorAll('.rel-filter-btn');
  btns.forEach(btn => {
    btn.addEventListener('click', function () {
      btns.forEach(b => b.classList.remove('active'));
      this.classList.add('active');
      const bucket = this.dataset.bucket || '';
      bar.dataset.active = bucket;
      onChange(bucket);
    });
  });
}

// Generic click-to-sort for any data-table: wires every <th class="th-sortable">
// in the table's header to reorder existing <tr> nodes in place (never rebuilds
// row HTML), so search/filter state (row.style.display) and modal data-bid-idx
// bindings survive sorting untouched. Reads each row's value for a column from
// that <td>'s data-sort-value attribute, falling back to its text content.
function initColumnSort(tableId, tbodyId) {
  const table = document.getElementById(tableId);
  const tbody = document.getElementById(tbodyId);
  if (!table || !tbody) return;
  const headerRow = table.querySelector('thead tr');
  if (!headerRow) return;
  const ths = Array.from(headerRow.children);

  function setIcon(th, desc, idle) {
    const icon = th.querySelector('.sort-icon');
    if (!icon) return;
    icon.className = 'bi ' + (desc ? 'bi-sort-down-alt' : 'bi-sort-up-alt') + ' sort-icon' + (idle ? ' sort-icon-idle' : '');
  }

  function clearOthers(exceptTh) {
    ths.forEach(function (th) {
      if (th === exceptTh || !th.classList.contains('th-sortable')) return;
      th.classList.remove('sort-active');
      delete th.dataset.sortDir;
      setIcon(th, true, true);
    });
  }

  function sortByColumn(th, desc) {
    const idx  = ths.indexOf(th);
    const type = th.dataset.sortType || 'text';
    const emptyRow = tbody.querySelector('tr.empty-row');
    const rows = Array.from(tbody.querySelectorAll('tr[data-searchable]'));
    rows.sort(function (a, b) {
      const ca = a.children[idx], cb = b.children[idx];
      let va = ca ? (ca.dataset.sortValue !== undefined ? ca.dataset.sortValue : ca.textContent.trim()) : '';
      let vb = cb ? (cb.dataset.sortValue !== undefined ? cb.dataset.sortValue : cb.textContent.trim()) : '';
      if (type === 'number') {
        va = parseFloat(va); if (isNaN(va)) va = -Infinity;
        vb = parseFloat(vb); if (isNaN(vb)) vb = -Infinity;
        return desc ? vb - va : va - vb;
      }
      va = String(va).toLowerCase(); vb = String(vb).toLowerCase();
      if (va < vb) return desc ? 1 : -1;
      if (va > vb) return desc ? -1 : 1;
      return 0;
    });
    rows.forEach(function (r) { tbody.insertBefore(r, emptyRow || null); });
    clearOthers(th);
    th.classList.add('sort-active');
    th.dataset.sortDir = desc ? 'desc' : 'asc';
    setIcon(th, desc, false);
  }

  ths.forEach(function (th) {
    if (!th.classList.contains('th-sortable')) return;
    th.addEventListener('click', function () {
      // Cycle: unsorted/desc -> ascending -> descending -> ascending ...
      sortByColumn(th, th.dataset.sortDir === 'asc');
    });
  });

  // Data arrives server-sorted to match the default column, so just mark it
  // active rather than re-sorting (avoids a redundant DOM reorder on load).
  const defaultTh = ths.find(function (th) { return th.dataset.sortDefault === 'desc'; });
  if (defaultTh) {
    defaultTh.classList.add('sort-active');
    defaultTh.dataset.sortDir = 'desc';
    setIcon(defaultTh, true, false);
  }

  // Exposed so callers can restore the default sort state after a table's
  // rows are rebuilt from freshly (server-)sorted data, e.g. on keyword change.
  table._resetColumnSort = function () {
    clearOthers(null);
    if (defaultTh) {
      defaultTh.classList.add('sort-active');
      defaultTh.dataset.sortDir = 'desc';
      setIcon(defaultTh, true, false);
    }
  };
}

function resetColumnSort(tableId) {
  const table = document.getElementById(tableId);
  if (table && typeof table._resetColumnSort === 'function') table._resetColumnSort();
}

// Combined search + relevance-bucket filter for the simple bid-list pages
// (awarded/technical/financial). Index page keeps its own applyTableFilters
// since it also has ministry/department dropdowns.
function initSearchWithRelevance(inputId, tableBodyId, countId, filterBarId) {
  const input   = document.getElementById(inputId);
  const tbody   = document.getElementById(tableBodyId);
  const countEl = countId ? document.getElementById(countId) : null;
  if (!tbody) return;
  let activeBucket = '';

  function apply() {
    const q        = (input?.value || '').toLowerCase().trim();
    const rows     = tbody.querySelectorAll('tr[data-searchable]');
    const emptyRow = tbody.querySelector('tr.empty-row');
    let visible = 0;
    rows.forEach(row => {
      const tm = !q || row.textContent.toLowerCase().includes(q);
      const rm = _relevanceMatches(row.dataset.relevance || 'none', activeBucket);
      const match = tm && rm;
      row.style.display = match ? '' : 'none';
      if (match) visible++;
    });
    if (countEl) countEl.textContent = visible;
    if (emptyRow) emptyRow.style.display = visible === 0 ? '' : 'none';
  }

  input?.addEventListener('input', apply);
  initRelevanceFilterBar(filterBarId, function (bucket) { activeBucket = bucket; apply(); });
  apply();
}

function _scoreChip(score) {
  if (score == null) return '<span style="color:var(--muted);font-size:0.8rem">—</span>';
  const s = parseInt(score, 10);
  const color  = s >= 85 ? '#2dc653' : (s >= 70 ? '#4cc9f0' : (s >= 40 ? '#ffd60a' : '#f72585'));
  const label  = s >= 85 ? 'Pursue'  : (s >= 70 ? 'Relevant' : (s >= 40 ? 'Consider' : 'Skip'));
  return `<span style="display:inline-flex;align-items:center;gap:4px;background:${color}22;border:1px solid ${color}55;color:${color};border-radius:20px;padding:2px 8px;font-size:0.72rem;font-weight:700">${s}<span style="font-weight:400;font-size:0.65rem;opacity:.85">${label}</span></span>`;
}

function _buildBidRow(bid, idx) {
  const catTag = bid.category === 'awarded'
    ? '<span class="tag tag-awarded">Awarded</span>'
    : bid.category === 'technical'
    ? '<span class="tag tag-technical">Technical</span>'
    : '<span class="tag tag-financial">Financial</span>';
  const priceColor = (bid.l1_price && bid.l1_price !== 'N/A') ? '#2dc653' : '#6c7293';
  const itemShort  = _esc(bid.items_short || '—');
  const itemFull   = _esc(bid.items_full  || bid.items_short || '');
  const ministry   = _esc(bid.ministry    || '—');
  const dept       = _esc(bid.department  || '—');
  const bidNo      = _esc(bid.bid_no      || '—');
  const price      = _esc(bid.l1_price    || 'N/A');
  const priceRaw   = bid.l1_price_raw != null ? bid.l1_price_raw : 0;
  const scoreVal   = bid.relevance_score != null ? bid.relevance_score : -1;
  const scoreCell  = _scoreChip(bid.relevance_score != null ? bid.relevance_score : null);
  const relBucket  = _relevanceBucket(bid.relevance_score != null ? bid.relevance_score : null);
  return `<tr data-searchable data-ministry="${ministry}" data-department="${dept}" data-relevance="${relBucket}">
    <td><span class="bid-no">${bidNo}</span></td>
    <td><div class="ministry-cell text-truncate" title="${ministry}">${ministry}</div></td>
    <td style="max-width:220px"><div class="text-truncate" title="${itemFull}" style="font-size:0.82rem;color:#c0c8e8">${itemShort}</div></td>
    <td>${catTag}</td>
    <td data-sort-value="${priceRaw}" style="color:${priceColor};font-weight:600;white-space:nowrap">${price}</td>
    <td data-sort-value="${scoreVal}" style="white-space:nowrap">${scoreCell}</td>
    <td><button class="btn-view" data-bs-toggle="modal" data-bs-target="#bidModal" data-bid-idx="${idx}"><i class="bi bi-eye me-1"></i>View</button></td>
  </tr>`;
}

function _updateVendorBars(vendors) {
  const container = document.getElementById('vendorBars');
  if (!container) return;
  if (!vendors || !vendors.length) {
    container.innerHTML = '<div style="color:#6c7293;font-size:0.8rem;padding:8px 0">No vendor data available</div>';
    return;
  }
  const max = vendors[0][1] || 1;
  container.innerHTML = vendors.map(([name, count]) => `
    <div class="d-flex align-items-center gap-2 mb-2" style="font-size:0.8rem">
      <div class="text-truncate" style="width:260px;color:#aab0d4;flex-shrink:0" title="${_esc(name)}">${_esc(name)}</div>
      <div class="flex-grow-1" style="background:#1b1d30;border-radius:4px;height:10px;overflow:hidden">
        <div style="width:${(count / max) * 100}%;height:100%;background:linear-gradient(90deg,#f72585,#7209b7);border-radius:4px"></div>
      </div>
      <div style="width:30px;text-align:right;color:#f72585;font-weight:700;flex-shrink:0">${count}</div>
    </div>`).join('');
}

function _updateMinistryBars(minCounts) {
  const container = document.getElementById('ministryBars');
  if (!container) return;
  if (!minCounts || !minCounts.length) {
    container.innerHTML = '<div style="color:#6c7293;font-size:0.8rem;padding:8px 0">No data</div>';
    return;
  }
  const max = minCounts[0][1] || 1;
  container.innerHTML = minCounts.map(([name, count]) => `
    <div class="d-flex align-items-center gap-2 mb-2" style="font-size:0.8rem">
      <div class="text-truncate" style="width:180px;color:#aab0d4;flex-shrink:0" title="${_esc(name)}">${_esc(name)}</div>
      <div class="flex-grow-1" style="background:#1b1d30;border-radius:4px;height:10px;overflow:hidden">
        <div style="width:${(count / max) * 100}%;height:100%;background:linear-gradient(90deg,#4361ee,#4cc9f0);border-radius:4px"></div>
      </div>
      <div style="width:24px;text-align:right;color:#8fa4ff;font-weight:700;flex-shrink:0">${count}</div>
    </div>`).join('');
}

function selectKeyword(keyword) {
  // Update sidebar active state
  document.querySelectorAll('.kw-link').forEach(el =>
    el.classList.toggle('active', el.dataset.kw === keyword)
  );

  fetch(`/api/keyword-data/${encodeURIComponent(keyword)}`)
    .then(r => r.json())
    .then(data => {
      if (data.error) return;

      // Stat cards
      const ids = {
        'stat-total':     data.total,
        'stat-awarded':   data.counts.awarded,
        'stat-technical': data.counts.technical,
        'stat-financial': data.counts.financial,
        'stat-value':     data.total_value,
      };
      Object.entries(ids).forEach(([id, val]) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      });

      // Top ministries mini bars
      _updateMinistryBars(data.min_counts);

      // Charts – update in place (no destroy/recreate flash)
      if (window.ministryChartInst) {
        window.ministryChartInst.data = data.ministry_chart;
        window.ministryChartInst.update();
      }
      if (window.statusChartInst) {
        window.statusChartInst.data = data.status_chart;
        window.statusChartInst.update();
      }

      // Rebuild table rows and re-bind search / filters
      window.BIDS_DATA = data.all_bids;
      const tbody = document.getElementById('allTableBody');
      if (tbody) {
        const emptyFallback = '<tr class="empty-row" style="display:none"><td colspan="7" class="empty-state"><i class="bi bi-search"></i>No results match your search</td></tr>';
        tbody.innerHTML = data.all_bids.length
          ? data.all_bids.map((b, i) => _buildBidRow(b, i)).join('') + emptyFallback
          : '<tr><td colspan="7" class="empty-state"><i class="bi bi-inbox"></i>No bids found</td></tr>' + emptyFallback;
      }

      if (typeof window._afterKeywordUpdate === 'function') {
        window._afterKeywordUpdate(data);
      } else if (tbody) {
        const searchInput = document.getElementById('allSearch');
        if (searchInput) searchInput.value = '';
        initSearch('allSearch', 'allTableBody', 'allSearch-count');
      }

      // Keyword badge near table title
      const badge = document.getElementById('activeKeywordBadge');
      if (badge) {
        if (keyword === '__all__') {
          badge.style.display = 'none';
        } else {
          badge.textContent = keyword.replace(/_/g, ' ');
          badge.style.display = '';
        }
      }
    })
    .catch(() => {});
}

/* ── Keyword click handlers + hash-based auto-select ────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.kw-link').forEach(el => {
    el.addEventListener('click', function (e) {
      e.preventDefault();
      const kw = this.dataset.kw;
      if (document.getElementById('allTableBody')) {
        // On index page: AJAX update
        selectKeyword(kw);
        history.replaceState(null, '',
          kw === '__all__' ? '/' : `/#kw=${encodeURIComponent(kw)}`);
      } else {
        // On other pages: navigate to index
        window.location.href =
          kw === '__all__' ? '/' : `/#kw=${encodeURIComponent(kw)}`;
      }
    });
  });

  // Auto-select keyword from URL hash when landing on index page
  if (document.getElementById('allTableBody')) {
    const hash = window.location.hash;
    if (hash.startsWith('#kw=')) {
      const kw = decodeURIComponent(hash.slice(4));
      if (kw) selectKeyword(kw);
    }
  }
});
