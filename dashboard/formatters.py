"""Presentation helpers: currency formatting, sorting keys, vendor ranking."""

import re


def parse_price(value):
    """Strip non-numeric chars and return float. Handles the rupee symbol."""
    cleaned = re.sub(r'[^\d.]', '', str(value or ''))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def fmt_price(value):
    v = parse_price(value)
    if v == 0:
        return 'N/A'
    if v >= 1e7:
        return f'₹{v / 1e7:.2f} Cr'
    if v >= 1e5:
        return f'₹{v / 1e5:.2f} L'
    return f'₹{v:,.0f}'


def fmt_total(value):
    """Show ₹0 instead of N/A when the total is zero."""
    return fmt_price(str(value)) if value > 0 else '₹0'


def shorten(text, length=60):
    return (text[:length] + '…') if text and len(text) > length else (text or '—')


def relevance_sort_key(bid):
    v = bid.get('relevance_score')
    return v if isinstance(v, (int, float)) else -1


def get_top_vendors(awarded_bids, top_n=10):
    counts = {}
    for b in awarded_bids:
        seller = b.get('l1_seller_full', '') or b.get('l1_seller', '') or ''
        if seller and seller.strip() not in ('', '—'):
            s = seller.strip()
            counts[s] = counts.get(s, 0) + 1
    return sorted(counts.items(), key=lambda x: -x[1])[:top_n]
