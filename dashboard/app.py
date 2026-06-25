import os
import json
import glob
import re
from datetime import datetime
from flask import Flask, render_template, jsonify

app = Flask(__name__)

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results'
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_price(s):
    """Strip non-numeric chars and return float. Handles backtick rupee symbol."""
    cleaned = re.sub(r'[^\d.]', '', str(s or ''))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def fmt_price(s):
    v = parse_price(s)
    if v == 0:
        return 'N/A'
    if v >= 1e7:
        return f'₹{v / 1e7:.2f} Cr'
    if v >= 1e5:
        return f'₹{v / 1e5:.2f} L'
    return f'₹{v:,.0f}'


def _shorten(text, n=60):
    return (text[:n] + '…') if text and len(text) > n else (text or '—')


# ── Data Loading ──────────────────────────────────────────────────────────────

def _bid_no_from_filename(fp):
    """Fallback: extract GEM/YYYY/T/NNNNNNN from filename when bid_details.bid_number is empty."""
    m = re.search(r'GEM_(\d+)_([A-Z])_(\d+)_', os.path.basename(fp))
    return f"GEM/{m.group(1)}/{m.group(2)}/{m.group(3)}" if m else ''


def load_category(cat):
    cat_dir = os.path.join(RESULTS_DIR, cat)
    summary = []
    sp = os.path.join(cat_dir, 'summary.json')
    if os.path.exists(sp):
        try:
            with open(sp, encoding='utf-8') as f:
                summary = json.load(f)
        except Exception:
            pass

    by_bid = {}
    for fp in glob.glob(os.path.join(cat_dir, '*_data.json')):
        try:
            with open(fp, encoding='utf-8') as f:
                d = json.load(f)
            bn = d.get('bid_details', {}).get('bid_number', '') or _bid_no_from_filename(fp)
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
        except Exception:
            pass

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
        raw_ministry = bd.get('ministry', '') or ''
        # Normalise inconsistent ministry strings from scraper
        if not raw_ministry or raw_ministry.strip() in ('', '-'):
            raw_ministry = '—'
        elif raw_ministry.lower() == 'pmo':
            raw_ministry = 'Prime Minister\'s Office'
        bids.append({
            **item,
            'detail': detail,
            'l1_price': fmt_price(l1_price_raw),
            'l1_price_raw': parse_price(l1_price_raw),
            'l1_seller': _shorten(l1_seller, 50),
            'l1_seller_full': l1_seller,
            'ministry': raw_ministry,
            'department': bd.get('department', '—') or '—',
            'organisation': bd.get('organisation', '—') or '—',
            'tech_count': len(detail.get('technical_evaluation', [])),
            'fin_count': len(detail.get('financial_evaluation', [])),
            'category': cat,
        })
    return bids


# ── Context Processor ─────────────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    return {'now': datetime.now().strftime('%d %b %Y')}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    awarded = load_category('awarded')
    technical = load_category('technical')
    financial = load_category('financial')

    all_bids = awarded + technical + financial
    total_value = sum(b['l1_price_raw'] for b in awarded)

    min_counts = {}
    for b in all_bids:
        m = b['ministry']
        min_counts[m] = min_counts.get(m, 0) + 1

    return render_template('index.html',
        total=len(all_bids),
        awarded=awarded,
        technical=technical,
        financial=financial,
        all_bids=all_bids,
        total_value=fmt_price(str(total_value)),
        min_counts=sorted(min_counts.items(), key=lambda x: -x[1])[:8],
    )


@app.route('/awarded')
def awarded_page():
    bids = load_category('awarded')
    return render_template('awarded.html', bids=bids)


@app.route('/technical')
def technical_page():
    bids = load_category('technical')
    return render_template('technical.html', bids=bids)


@app.route('/financial')
def financial_page():
    bids = load_category('financial')
    return render_template('financial.html', bids=bids)


# ── API Endpoints (Chart.js) ──────────────────────────────────────────────────

@app.route('/api/ministry-chart')
def ministry_chart():
    all_bids = (
        load_category('awarded') + load_category('technical') + load_category('financial')
    )
    counts = {}
    for b in all_bids:
        m = b['ministry']
        if m == '—':
            m = 'Unknown / Not Specified'
        else:
            # Strip leading "Ministry Of/of " prefix for chart brevity
            m = re.sub(r'^Ministry\s+[Oo]f\s+', '', m).strip()
            m = re.sub(r'^Ministry\s+', '', m).strip()
        if len(m) > 30:
            m = m[:28] + '…'
        counts[m] = counts.get(m, 0) + 1

    data = sorted(counts.items(), key=lambda x: -x[1])[:10]
    palette = ['#4361ee', '#7209b7', '#3a0ca3', '#f72585', '#4cc9f0',
               '#4895ef', '#560bad', '#b5179e', '#f3722c', '#43aa8b']
    return jsonify({
        'labels': [d[0] for d in data],
        'datasets': [{
            'label': 'Bids',
            'data': [d[1] for d in data],
            'backgroundColor': palette[:len(data)],
            'borderWidth': 0,
            'borderRadius': 6,
        }]
    })


@app.route('/api/status-chart')
def status_chart():
    a = load_category('awarded')
    t = load_category('technical')
    f = load_category('financial')
    return jsonify({
        'labels': ['Awarded', 'Technical Eval', 'Financial Eval'],
        'datasets': [{
            'data': [len(a), len(t), len(f)],
            'backgroundColor': ['#2dc653', '#ffd60a', '#4cc9f0'],
            'borderColor': '#161826',
            'borderWidth': 3,
            'hoverOffset': 8,
        }]
    })


if __name__ == '__main__':
    print('\n  GeM Tender Intelligence Dashboard')
    print('  Running at  →  http://localhost:5000\n')
    app.run(debug=True, port=5000)
