"""Flask dashboard for exploring scraped and relevance-scored GeM tenders."""

import logging
import re
from datetime import datetime

from flask import Flask, render_template, jsonify

from data_loader import get_keywords, load_category, load_category_bids, load_keyword_data
from formatters import fmt_total, get_top_vendors, relevance_sort_key

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

app = Flask(__name__)

CHART_PALETTE = ['#4361ee', '#7209b7', '#3a0ca3', '#f72585', '#4cc9f0',
                 '#4895ef', '#560bad', '#b5179e', '#f3722c', '#43aa8b']
STATUS_COLORS = ['#2dc653', '#ffd60a', '#4cc9f0']


# ── Helpers ──────────────────────────────────────────────────────────────────

def _short_ministry(ministry, max_len=30):
    """Strip the "Ministry Of/of " prefix and truncate for chart labels."""
    label = 'Unknown / Not Specified' if ministry == '—' else ministry
    label = re.sub(r'^Ministry\s+[Oo]f\s+', '', label).strip()
    label = re.sub(r'^Ministry\s+', '', label).strip()
    if len(label) > max_len:
        label = label[:max_len - 2] + '…'
    return label


def _ministry_chart_data(bids):
    counts = {}
    for b in bids:
        m = _short_ministry(b['ministry'])
        counts[m] = counts.get(m, 0) + 1
    data = sorted(counts.items(), key=lambda x: -x[1])[:10]
    return {
        'labels': [d[0] for d in data],
        'datasets': [{
            'label': 'Bids',
            'data': [d[1] for d in data],
            'backgroundColor': CHART_PALETTE[:len(data)],
            'borderWidth': 0,
            'borderRadius': 6,
        }],
    }


def _status_chart_data(awarded, technical, financial):
    return {
        'labels': ['Awarded', 'Technical Eval', 'Financial Eval'],
        'datasets': [{
            'data': [len(awarded), len(technical), len(financial)],
            'backgroundColor': STATUS_COLORS,
            'borderColor': '#161826',
            'borderWidth': 3,
            'hoverOffset': 8,
        }],
    }


# ── Context Processor ─────────────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    return {
        'now': datetime.now().strftime('%d %b %Y'),
        'keywords': get_keywords(),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    awarded = load_category('awarded')
    technical = load_category('technical')
    financial = load_category('financial')

    # When category dirs are absent, aggregate across all keyword folders
    if not (awarded or technical or financial):
        for kw in get_keywords():
            d = load_keyword_data(kw)
            awarded += d['awarded']
            technical += d['technical']
            financial += d['financial']

    all_bids = awarded + technical + financial
    all_bids.sort(key=relevance_sort_key, reverse=True)
    total_value = sum(b['l1_price_raw'] for b in awarded)

    min_counts = {}
    for b in all_bids:
        m = b['ministry']
        min_counts[m] = min_counts.get(m, 0) + 1

    top_vendors = get_top_vendors(awarded)
    ministries = sorted(set(b['ministry'] for b in all_bids if b.get('ministry') and b['ministry'] != '—'))
    departments = sorted(set(b['department'] for b in all_bids if b.get('department') and b['department'] != '—'))

    return render_template('index.html',
        total=len(all_bids),
        awarded=awarded,
        technical=technical,
        financial=financial,
        all_bids=all_bids,
        total_value=fmt_total(total_value),
        min_counts=sorted(min_counts.items(), key=lambda x: -x[1])[:8],
        top_vendors=top_vendors,
        ministries=ministries,
        departments=departments,
    )


@app.route('/awarded')
def awarded_page():
    bids = load_category_bids('awarded')
    return render_template('awarded.html', bids=bids)


@app.route('/technical')
def technical_page():
    bids = load_category_bids('technical')
    return render_template('technical.html', bids=bids)


@app.route('/financial')
def financial_page():
    bids = load_category_bids('financial')
    return render_template('financial.html', bids=bids)


# ── API Endpoints (Chart.js) ──────────────────────────────────────────────────

@app.route('/api/ministry-chart')
def ministry_chart():
    all_bids = load_category('awarded') + load_category('technical') + load_category('financial')
    return jsonify(_ministry_chart_data(all_bids))


@app.route('/api/status-chart')
def status_chart():
    a = load_category('awarded')
    t = load_category('technical')
    f = load_category('financial')
    return jsonify(_status_chart_data(a, t, f))


@app.route('/api/keyword-data/<keyword>')
def api_keyword_data(keyword):
    valid = get_keywords()

    if keyword == '__all__':
        awarded, technical, financial = [], [], []
        for kw in valid:
            d = load_keyword_data(kw)
            awarded += d['awarded']
            technical += d['technical']
            financial += d['financial']
    elif keyword not in valid:
        return jsonify({'error': 'Unknown keyword'}), 404
    else:
        d = load_keyword_data(keyword)
        awarded, technical, financial = d['awarded'], d['technical'], d['financial']

    all_bids = awarded + technical + financial
    all_bids.sort(key=relevance_sort_key, reverse=True)
    total_value = sum(b['l1_price_raw'] for b in awarded)
    top_vendors = get_top_vendors(awarded)

    top_m = {}
    for b in all_bids:
        top_m[b['ministry']] = top_m.get(b['ministry'], 0) + 1
    tmd = sorted(top_m.items(), key=lambda x: -x[1])[:8]

    return jsonify({
        'all_bids': all_bids,
        'total': len(all_bids),
        'total_value': fmt_total(total_value),
        'top_vendors': top_vendors,
        'counts': {
            'awarded': len(awarded),
            'technical': len(technical),
            'financial': len(financial),
        },
        'min_counts': tmd,
        'ministry_chart': _ministry_chart_data(all_bids),
        'status_chart': _status_chart_data(awarded, technical, financial),
    })


if __name__ == '__main__':
    logging.info("GeM Tender Intelligence Dashboard")
    logging.info("Running at -> http://localhost:5000")
    app.run(debug=True, port=5000)
