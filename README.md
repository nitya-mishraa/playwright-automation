# GeM Tender Intelligence Platform

A Tender Intelligence platform built on top of GeM BidPlus data extraction.

This project consists of:

1. **Scraper** (`main.py` + `scraper/`) – Playwright-based scraper for extracting GeM BidPlus tender data.
2. **Relevance Scorer** (`score_bids.py`) – Local LLM-powered engine that scores each tender against a company profile.
3. **Flask Dashboard** (`dashboard/`) – Interactive dashboard for exploring awarded, technical, and financial bid intelligence.

---

# Features

### Scraper

- Keyword-based GeM BidPlus search
- Service Bid filtering
- Dynamic pagination
- Awarded Bid extraction
- Technical Evaluation extraction
- Financial Evaluation extraction
- Structured JSON output
- Unlimited or limited page scraping

### Dashboard

- Dark professional UI
- Keyword-based navigation
- Awarded / Technical / Financial views
- Search functionality
- Ministry filtering
- Department filtering
- Bid detail modal
- Interactive charts
- Responsive layout

---

# Installation

## Create Virtual Environment

```bash
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Install Playwright Browser

```bash
playwright install chromium
```

---

# Running The Scraper

Run scraper for any keyword:

```bash
python main.py -k AI
```

Examples:

```bash
python main.py -k Intelligence

python main.py -k Drone

python main.py -k Cyber

python main.py -k Floods

python main.py -k GIS

python main.py -k Satellite

python main.py -k Analytics
```

For unlimited pages:

```bash
python main.py -k Intelligence -p 0
```

---

# Running The Dashboard

```bash
cd dashboard

python app.py
```

Open:

```text
http://localhost:5000
```

---
# Relevance Intelligence

The platform includes a local LLM-powered relevance scoring engine that evaluates each tender against the company's capabilities (defined in `company_profile.json`).

### Scoring Categories

| Score | Category |
|---------|---------|
| 85-100 | Pursue |
| 70-84 | Relevant |
| 40-69 | Consider |
| 0-39 | Skip |

### Output Fields

Each bid is enriched with:

- relevance_score
- matching_capabilities
- missing_capabilities
- recommendation

## Running Relevance Scoring

```bash
python score_bids.py --keyword AI
```

---

# Output Structure

```text
results/
├── AI/
│   ├── awarded_summary.json
│   ├── technical_summary.json
│   └── financial_summary.json
│
├── Cyber/
│   ├── awarded_summary.json
│   ├── technical_summary.json
│   └── financial_summary.json
│
├── Drone/
│   ├── awarded_summary.json
│   ├── technical_summary.json
│   └── financial_summary.json
│
└── Floods/
    ├── awarded_summary.json
    ├── technical_summary.json
    └── financial_summary.json
```

---

# Dashboard Capabilities

- View all extracted bids
- Keyword-wise intelligence
- Awarded bid analysis
- Technical evaluation analysis
- Financial evaluation analysis
- Ministry-level insights
- Department-level insights
- Bid-level detailed view
- L1 bidder analysis
- Tender intelligence exploration

### Relevance Features

- Relevance Score column
- Pursue / Relevant / Consider / Skip filters
- Category-wise counts
- Default relevance-based ranking
- Click-to-sort columns (Ascending / Descending)

---

# Project Structure

```text
playwright-automation/
│
├── main.py                    # Scraper entry point (single, thin CLI wrapper)
├── score_bids.py               # Relevance scoring CLI (local LLM)
├── company_profile.json        # Company capability profile used for scoring
├── requirements.txt             # Consolidated dependencies for scraper + scorer + dashboard
├── .gitignore
├── README.md
│
├── scraper/                     # Scraper package
│   ├── __init__.py
│   ├── config.py                 # Config dataclass, defaults, CLI arg parsing
│   ├── browser_scripts.py        # In-page JS snippets used via page.evaluate
│   ├── html_parser.py            # HTML -> structured bid data parsing
│   └── pipeline.py               # Search/filter, pagination, scraping, orchestration
│
├── dashboard/                    # Flask dashboard
│   ├── app.py                     # Routes and API endpoints only
│   ├── data_loader.py             # Loading/merging bid JSON from results/
│   ├── formatters.py              # Currency formatting, sorting, vendor ranking
│   ├── run.bat
│   ├── templates/
│   └── static/
│
└── results/                      # Scraped + scored tender data, one folder per keyword
```

---
# Architecture
```text
GeM BidPlus
     ↓
Playwright Scraper (scraper/)
     ↓
Structured JSON (results/)
     ↓
Local LLM Relevance Engine (score_bids.py)
     ↓
Enhanced Bid Intelligence
     ↓
Flask Dashboard (dashboard/)
```
---
# Impact

- Automated extraction of Technical Evaluation and Financial Evaluation information from GeM.
- Automated tender relevance assessment using a local LLM.
- Reduced manual tender review effort through intelligent bid prioritization.
- Enabled keyword-wise exploration and analytics through an interactive dashboard.

---

# Future Enhancements

- Local LLM based filtering
- Natural language tender search
- Semantic bid retrieval
- AI-powered tender intelligence
- Advanced analytics and reporting

---

# Tech Stack

- Python
- Playwright
- BeautifulSoup
- Flask
- Bootstrap
- Chart.js
- JSON

---
