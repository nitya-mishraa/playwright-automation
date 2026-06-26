
# GeM Tender Intelligence Platform

A Tender Intelligence platform built on top of GeM BidPlus data extraction.

This project consists of:

1. **main.py** – Playwright-based scraper for extracting GeM BidPlus tender data.
2. **Flask Dashboard** – Interactive dashboard for exploring awarded, technical, and financial bid intelligence.
3. **Keyword Intelligence System** – Organizes results keyword-wise for targeted analysis.

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

---

# Project Structure

```text
playwright-automation/
│
├── main.py
├── main_sir.py
├── README.md
├── downloads/
├── results/
│
└── dashboard/
    ├── app.py
    ├── requirements.txt
    ├── templates/
    └── static/
```

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

