"""In-page JavaScript snippets evaluated via Playwright's ``page.evaluate``."""

CARD_EXTRACT_JS = """() => {
    const out = [];
    document.querySelectorAll('.card').forEach(card => {
        if (!card.querySelector('.block_header')) return;
        const bidLinks = Array.from(card.querySelectorAll('.block_header a.bid_no_hover')).map(a => ({
            label: (a.previousElementSibling && a.previousElementSibling.innerText || '').trim(),
            text: a.innerText.trim(),
            href: a.getAttribute('href') || ''
        }));
        const itemsEl = card.querySelector('a[data-toggle="popover"]');
        const statusEl = card.querySelector('.block_header .text-success, .block_header .text-danger');
        const rows = Array.from(card.querySelectorAll('.card-body .row .row, .card-body > .row > div > .row'))
            .map(r => r.innerText.replace(/\\s+/g, ' ').trim())
            .filter(Boolean);
        const resultButtons = Array.from(card.querySelectorAll('a[href*="ResultView/"]')).map(a => {
            const btn = a.querySelector('input[type="button"]');
            return {
                label: btn ? (btn.value || '').trim() : a.innerText.trim(),
                href: a.getAttribute('href') || ''
            };
        });
        out.push({
            bid_links: bidLinks,
            status: statusEl ? statusEl.innerText.trim() : '',
            items_short: itemsEl ? itemsEl.innerText.trim() : '',
            items_full: itemsEl ? (itemsEl.getAttribute('data-content') || '') : '',
            items_category: itemsEl ? (itemsEl.getAttribute('data-original-title') || '') : '',
            rows: rows,
            result_buttons: resultButtons
        });
    });
    return out;
}"""

# Returns True when a non-disabled "Next" control exists in the pagination bar.
PAGINATION_HAS_NEXT_JS = """() => {
    return !!document.querySelector('#light-pagination a.next');
}"""

# Clicks the "Next" control and returns true on success.
PAGINATION_CLICK_NEXT_JS = """() => {
    const nextBtn = document.querySelector('#light-pagination a.next');
    if (nextBtn) {
        nextBtn.click();
        return true;
    }
    return false;
}"""

# Returns {current, total} page numbers visible in the pagination bar.
PAGINATION_INFO_JS = """() => {
    const current = document.querySelector('#light-pagination .current');
    return {
        current: current ? parseInt(current.textContent.trim()) : 1,
        total: null
    };
}"""

# Force-open every Bootstrap collapse panel so all sections render.
EXPAND_PANELS_JS = """() => {
    let n = 0;
    document.querySelectorAll('.panel-collapse').forEach(el => {
        if (!el.classList.contains('in')) { el.classList.add('in'); n++; }
        el.style.height = '';
        el.style.display = '';
        el.setAttribute('aria-expanded', 'true');
    });
    document.querySelectorAll('[data-toggle="collapse"]').forEach(t => {
        t.setAttribute('aria-expanded', 'true');
        t.classList.remove('collapsed');
    });
    return n;
}"""
