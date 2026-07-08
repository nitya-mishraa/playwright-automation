"""Reads scraped/scored bid data from the results/ directory tree."""

import glob
import json
import logging
import os
import re

from formatters import parse_price, fmt_price, shorten, relevance_sort_key

logger = logging.getLogger(__name__)

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results'
)

CATEGORIES = ('awarded', 'technical', 'financial')


def bid_no_from_filename(fp):
    """Fallback: extract GEM/YYYY/T/NNNNNNN from filename when bid_details.bid_number is empty."""
    m = re.search(r'GEM_(\d+)_([A-Z])_(\d+)_', os.path.basename(fp))
    return f"GEM/{m.group(1)}/{m.group(2)}/{m.group(3)}" if m else ''


def _normalize_ministry(raw_ministry):
    raw_ministry = (raw_ministry or '').strip()
    if not raw_ministry or raw_ministry == '-':
        return '—'
    if raw_ministry.lower() == 'pmo':
        return "Prime Minister's Office"
    return raw_ministry


def get_keywords():
    """Return sorted list of keyword subdirectories found in results/."""
    if not os.path.isdir(RESULTS_DIR):
        return []
    return sorted(
        d for d in os.listdir(RESULTS_DIR)
        if os.path.isdir(os.path.join(RESULTS_DIR, d))
    )


def load_keyword_data(keyword):
    """Load awarded/technical/financial *_summary.json for a keyword folder.
    Missing files silently return empty lists — never raises."""
    kw_dir = os.path.join(RESULTS_DIR, keyword)
    result = {}
    for cat in CATEGORIES:
        fp = os.path.join(kw_dir, f'{cat}_summary.json')
        items = []
        if os.path.exists(fp):
            try:
                with open(fp, encoding='utf-8') as f:
                    raw = json.load(f)
                for item in (raw if isinstance(raw, list) else []):
                    text = str(item.get('items', '') or '')

                    # Build detail by merging all nested result entries
                    detail = {
                        'bid_details': {},
                        'buyer_details': {},
                        'technical_evaluation': [],
                        'financial_evaluation': [],
                    }
                    for res in item.get('results', []):
                        d = res.get('data') or {}
                        if not detail['bid_details'] and d.get('bid_details'):
                            detail['bid_details'] = d['bid_details']
                        if not detail['buyer_details'] and d.get('buyer_details'):
                            detail['buyer_details'] = d['buyer_details']
                        detail['technical_evaluation'].extend(d.get('technical_evaluation') or [])
                        detail['financial_evaluation'].extend(d.get('financial_evaluation') or [])

                    # Extract L1 price from financial_evaluation (rank == "L1")
                    l1_price_raw = 0.0
                    l1_seller = '—'
                    for fe in detail['financial_evaluation']:
                        if fe.get('rank') == 'L1':
                            l1_price_raw = parse_price(fe.get('total_price', ''))
                            l1_seller = fe.get('seller_name', '—') or '—'
                            break

                    buy = detail['buyer_details']
                    department = buy.get('department', '—') or '—'

                    items.append({
                        **item,
                        'items_short': shorten(text, 60),
                        'items_full': text,
                        'category': cat,
                        'keyword': keyword,
                        'ministry': _normalize_ministry(buy.get('ministry', '')),
                        'department': department,
                        'organisation': buy.get('organisation', '—') or '—',
                        'l1_price': fmt_price(str(l1_price_raw)) if l1_price_raw > 0 else 'N/A',
                        'l1_price_raw': l1_price_raw,
                        'l1_seller': shorten(l1_seller, 50),
                        'l1_seller_full': l1_seller,
                        'tech_count': len(detail['technical_evaluation']),
                        'fin_count': len(detail['financial_evaluation']),
                        'detail': detail,
                    })
            except Exception as exc:
                logger.warning("Failed to load %s: %s", fp, exc)
        result[cat] = items
    return result


def load_category(cat):
    cat_dir = os.path.join(RESULTS_DIR, cat)
    summary = []
    sp = os.path.join(cat_dir, 'summary.json')
    if os.path.exists(sp):
        try:
            with open(sp, encoding='utf-8') as f:
                summary = json.load(f)
        except Exception as exc:
            logger.warning("Failed to load %s: %s", sp, exc)

    by_bid = {}
    for fp in glob.glob(os.path.join(cat_dir, '*_data.json')):
        try:
            with open(fp, encoding='utf-8') as f:
                d = json.load(f)
            bn = d.get('bid_details', {}).get('bid_number', '') or bid_no_from_filename(fp)
            if not bn:
                continue
            if bn not in by_bid:
                by_bid[bn] = {
                    'bid_details': d.get('bid_details', {}),
                    'buyer_details': d.get('buyer_details', {}),
                    'technical_evaluation': [],
                    'financial_evaluation': [],
                }
            # Merge multiple result files per bid (BID + RA)
            by_bid[bn]['technical_evaluation'] += d.get('technical_evaluation', [])
            by_bid[bn]['financial_evaluation'] += d.get('financial_evaluation', [])
        except Exception as exc:
            logger.warning("Failed to load %s: %s", fp, exc)

    bids = []
    for item in summary:
        bn = item.get('bid_no', '')
        detail = by_bid.get(bn, {})

        # Find L1 entry
        l1_price_raw, l1_seller = '', ''
        for r in detail.get('financial_evaluation', []):
            if r.get('rank') == 'L1':
                l1_price_raw = r.get('total_price', '')
                l1_seller = r.get('seller_name', '')
                break

        bd = detail.get('buyer_details', {})
        bids.append({
            **item,
            'detail': detail,
            'l1_price': fmt_price(l1_price_raw),
            'l1_price_raw': parse_price(l1_price_raw),
            'l1_seller': shorten(l1_seller, 50),
            'l1_seller_full': l1_seller,
            'ministry': _normalize_ministry(bd.get('ministry', '')),
            'department': bd.get('department', '—') or '—',
            'organisation': bd.get('organisation', '—') or '—',
            'tech_count': len(detail.get('technical_evaluation', [])),
            'fin_count': len(detail.get('financial_evaluation', [])),
            'category': cat,
        })
    return bids


def load_category_bids(cat):
    """Load bids for a top-level category page ('awarded'/'technical'/'financial'),
    falling back to aggregating across keyword folders when no top-level
    results/<cat>/ directory exists (the scraper currently only writes
    results/<keyword>/<cat>_summary.json). Always sorted by relevance
    descending (unscored bids last)."""
    bids = load_category(cat)
    if not bids:
        bids = []
        for kw in get_keywords():
            bids += load_keyword_data(kw)[cat]
    bids.sort(key=relevance_sort_key, reverse=True)
    return bids
