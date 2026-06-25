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
});

/* ── Live Table Search ─────────────────────────────────────────────────── */
function initSearch(inputId, tableBodyId, countId) {
  const input = document.getElementById(inputId);
  const tbody = document.getElementById(tableBodyId);
  const countEl = countId ? document.getElementById(countId) : null;
  if (!input || !tbody) return;

  const allRows = Array.from(tbody.querySelectorAll('tr[data-searchable]'));
  const emptyRow = tbody.querySelector('tr.empty-row');
  const total = allRows.length;

  if (countEl) countEl.textContent = total;

  input.addEventListener('input', function () {
    const q = this.value.toLowerCase().trim();
    let visible = 0;
    allRows.forEach(row => {
      const match = !q || row.textContent.toLowerCase().includes(q);
      row.style.display = match ? '' : 'none';
      if (match) visible++;
    });
    if (countEl) countEl.textContent = visible;
    if (emptyRow) emptyRow.style.display = visible === 0 ? '' : 'none';
  });
}

/* ── Modal Population (generic) ────────────────────────────────────────── */
function setModalField(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value || '—';
}

function populateBidModal(bid) {
  if (!bid) return;
  const bd  = bid.detail?.bid_details   || {};
  const buy = bid.detail?.buyer_details  || {};
  const te  = bid.detail?.technical_evaluation || [];
  const fe  = bid.detail?.financial_evaluation || [];

  setModalField('m-bid-no',       bid.bid_no);
  setModalField('m-status',       bid.status);
  setModalField('m-item',         bid.items_full || bid.items_short);
  setModalField('m-quantity',     bd.bid_quantity || bd.quantity);
  setModalField('m-bid-start',    bd.bid_start_datetime);
  setModalField('m-bid-end',      bd.bid_end_datetime);
  setModalField('m-bid-open',     bd.bid_opening_datetime);
  setModalField('m-bid-validity', bd.bid_validity_days ? bd.bid_validity_days + ' days' : '');
  setModalField('m-ministry',     buy.ministry);
  setModalField('m-department',   buy.department);
  setModalField('m-org',          buy.organisation);
  setModalField('m-office',       buy.office);
  setModalField('m-buyer-name',   buy.name);

  // Technical Evaluation Table
  const tBody = document.getElementById('m-tech-tbody');
  if (tBody) {
    if (te.length) {
      tBody.innerHTML = te.map(r => `
        <tr>
          <td>${r.sr_no || ''}</td>
          <td>${r.seller_name || '—'}</td>
          <td class="text-truncate" style="max-width:180px" title="${(r.offered_item||'').replace(/"/g,"'")}">${r.offered_item || '—'}</td>
          <td>${r.participated_on || '—'}</td>
          <td><span class="tag tag-mse">${r.mse_mii_status ? 'MSE/MII' : '—'}</span></td>
          <td><span class="tag tag-qualified">${r.status || '—'}</span></td>
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
        const rankClass = ['L1','L2','L3'].includes(r.rank) ? `rank-${r.rank}` : 'rank-xx';
        const price = r.total_price || '';
        return `
        <tr>
          <td>${r.sr_no || ''}</td>
          <td>${r.seller_name || '—'}</td>
          <td>${price.replace('`','₹')}</td>
          <td><span class="rank-badge ${rankClass}">${r.rank || '—'}</span></td>
        </tr>`;
      }).join('');
    } else {
      fBody.innerHTML = '<tr><td colspan="4" class="text-center text-secondary py-3">No data</td></tr>';
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
