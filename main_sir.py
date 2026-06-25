from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
import argparse
import json
import os
import re
import shutil
import time

# ── Configuration ───────────────────────────────────────────────────────────
@dataclass
class Config:
    """Runtime configuration for a scraping run.

    Construct with overrides (e.g. ``Config(keyword="Drone", max_pages=5)``)
    or call :func:`default_config` for the built-in defaults.
    """
    keyword: str = "Intelligence"
    max_pages: int | None = 3  # safety ceiling – set to None to disable
    base_url: str = "https://bidplus.gem.gov.in/all-bids"
    download_dir: str = "./downloads"
    results_dir: str = "./results"
    # By Bid Type: only "Service Bid/RAs" (checkbox id on the page)
    bid_type_checkbox: str = "service"
    headless: bool = False
    # (checkbox id on the page, output subfolder name)
    statuses: list[tuple[str, str]] = field(default_factory=lambda: [
        ("bid_awarded", "awarded"),
        ("tech_evaluated", "technical"),
        ("fin_evaluated", "financial"),
    ])


def default_config():
    """Return a Config populated entirely with built-in defaults."""
    return Config()


# ── Generic helpers ─────────────────────────────────────────────────────────
def safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")


def prune_empty(obj):
    """Recursively remove empty values ("", None, [], {}) from dicts/lists."""
    empties = ("", None, [], {})
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            pv = prune_empty(v)
            if pv not in empties:
                out[k] = pv
        return out
    if isinstance(obj, list):
        out = []
        for v in obj:
            pv = prune_empty(v)
            if pv not in empties:
                out.append(pv)
        return out
    return obj


def absolutize(href):
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if not href.startswith("/"):
        href = "/" + href
    return f"https://bidplus.gem.gov.in{href}"


def detect_page_type(title):
    title = title.lower()
    if "national public procurement portal" in title:
        return "homepage"
    if "gem" in title and "bidding" in title:
        return "information"
    return "unknown"


# ── HTML parsing ────────────────────────────────────────────────────────────
def extract_bid_data(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    data = {
        "bid_details": {},
        "buyer_details": {},
        "technical_evaluation": [],
        "financial_evaluation": [],
    }

    # Bid Details
    bid_no = re.search(r"Bid Number:\s*(GEM/\d+/B/\d+)", text)
    if bid_no:
        data["bid_details"]["bid_number"] = bid_no.group(1)

    bid_status = re.search(r"Bid Status:\s*([A-Za-z]+)", text)
    if bid_status:
        data["bid_details"]["bid_status"] = bid_status.group(1)

    quantity = re.search(r"Quantity:\s*(\d+)", text)
    if quantity:
        data["bid_details"]["quantity"] = quantity.group(1)

    start_date = re.search(r"Bid Start Date\s*/\s*Time:\s*([0-9:\-\s]+)", text)
    if start_date:
        data["bid_details"]["bid_start_datetime"] = start_date.group(1).strip()

    end_date = re.search(r"Bid End Date\s*/\s*Time:\s*([0-9:\-\s]+)", text)
    if end_date:
        data["bid_details"]["bid_end_datetime"] = end_date.group(1).strip()

    opening_date = re.search(r"Bid Opening Date\s*/\s*Time:\s*([0-9:\-\s]+)", text)
    if opening_date:
        data["bid_details"]["bid_opening_datetime"] = opening_date.group(1).strip()

    turnover = re.search(r"Average Turn Over Of Last 3 Years:\s*(.*?)\s*Experience", text)
    if turnover:
        data["bid_details"]["average_turnover_last_3_years"] = turnover.group(1).strip()

    experience = re.search(r"Experience with Gov\. Required:\s*(\w+)", text)
    if experience:
        data["bid_details"]["experience_with_gov_required"] = experience.group(1).strip()

    validity = re.search(r"Bid Validity .*?:\s*(\d+)", text)
    if validity:
        data["bid_details"]["bid_validity_days"] = validity.group(1)

    # Buyer Details
    buyer_section = text[text.find("Buyer Details"):]

    name = re.search(r"Name:\s*(.*?)\s*Address:", buyer_section, re.S)
    if name:
        data["buyer_details"]["name"] = name.group(1).strip()

    address = re.search(r"Address:\s*(.*?)\s*Ministry:", buyer_section, re.S)
    if address:
        data["buyer_details"]["address"] = address.group(1).strip()

    ministry = re.search(r"Ministry:\s*(.*?)\s*Department:", buyer_section, re.S)
    if ministry:
        data["buyer_details"]["ministry"] = ministry.group(1).strip()

    department = re.search(r"Department:\s*(.*?)\s*Organisation:", buyer_section, re.S)
    if department:
        data["buyer_details"]["department"] = department.group(1).strip()

    organisation = re.search(r"Organisation:\s*(.*?)\s*Office:", buyer_section, re.S)
    if organisation:
        data["buyer_details"]["organisation"] = organisation.group(1).strip()

    office = re.search(r"Office:\s*(.*)", buyer_section)
    if office:
        data["buyer_details"]["office"] = office.group(1).strip()

    # Technical Evaluation
    tables = soup.find_all("table")
    for table in tables:
        headers = [th.get_text(" ", strip=True).lower() for th in table.find_all("th")]
        if "seller name" in " ".join(headers):
            rows = table.find_all("tr")[1:]
            for row in rows:
                cols = [td.get_text(" ", strip=True) for td in row.find_all("td")]
                if len(cols) >= 6:
                    data["technical_evaluation"].append({
                        "sr_no": cols[0],
                        "seller_name": cols[1],
                        "offered_item": cols[2],
                        "participated_on": cols[3],
                        "mse_mii_status": cols[4],
                        "status": cols[5],
                    })

    # Financial Evaluation
    for table in tables:
        headers = [th.get_text(" ", strip=True).lower() for th in table.find_all("th")]
        if "total price" in " ".join(headers) and "rank" in " ".join(headers):
            rows = table.find_all("tr")[1:]
            for row in rows:
                cols = [td.get_text(" ", strip=True) for td in row.find_all("td")]
                if len(cols) >= 5:
                    data["financial_evaluation"].append({
                        "sr_no": cols[0],
                        "seller_name": cols[1],
                        "offered_item": cols[2],
                        "total_price": cols[3],
                        "rank": cols[4],
                    })

    return data


# ── Page-side JavaScript snippets ───────────────────────────────────────────
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


# ── Search / filtering ──────────────────────────────────────────────────────
def open_filtered_search(context, checkbox_id, cfg):
    """Open a fresh page, apply Bid/RA status + Service bid-type filters,
    search cfg.keyword and wait for results."""
    page = context.new_page()
    print("Opening GeM BidPlus...")
    page.goto(cfg.base_url, wait_until="networkidle")

    print("Switching to Bid/RA Status tab...")
    page.evaluate("document.getElementById('bidrastatus').click()")
    time.sleep(1)

    print(f"Ticking {checkbox_id}...")
    page.evaluate(f"document.getElementById('{checkbox_id}').click()")
    time.sleep(2)

    print("Selecting Bid Type: Service Bid/RAs...")
    page.evaluate(f"document.getElementById('{cfg.bid_type_checkbox}').click()")
    time.sleep(2)

    print(f"Searching keyword: {cfg.keyword}")
    search_input = page.locator("#searchBid")
    search_input.fill(cfg.keyword)
    search_input.press("Enter")

    page.wait_for_load_state("networkidle")
    time.sleep(3)
    return page


# ── Card collection (pagination) ────────────────────────────────────────────
def collect_cards(page, cfg):
    """Walk every result page and return the collected bid cards."""
    all_cards = []
    page_num = 1

    while True:
        print(page.locator("#light-pagination").inner_text())
        pg_info = page.evaluate(PAGINATION_INFO_JS)
        total_label = f"/{pg_info['total']}" if pg_info["total"] else ""
        print(f"Extracting bid cards – page {page_num}{total_label} ...")

        batch = page.evaluate(CARD_EXTRACT_JS)
        print(f"  {len(batch)} card(s) on this page")

        for c in batch:
            for bl in c["bid_links"]:
                bl["url"] = absolutize(bl["href"])
            for rb in c["result_buttons"]:
                rb["url"] = absolutize(rb["href"])
            c["bid_no"] = c["bid_links"][0]["text"] if c["bid_links"] else ""
            c["source_page"] = page_num

        all_cards.extend(batch)

        if not batch:
            print("  Empty page – stopping pagination.")
            break
        if cfg.max_pages and page_num >= cfg.max_pages:
            print(f"  Reached max_pages={cfg.max_pages} – stopping pagination.")
            break

        if not page.evaluate(PAGINATION_HAS_NEXT_JS):
            print("  No further pages detected.")
            break

        print("  Navigating to next page...")
        if not page.evaluate(PAGINATION_CLICK_NEXT_JS):
            break

        time.sleep(2)
        page_num += 1

    print(f"Total bid cards collected across {page_num} page(s): {len(all_cards)}")
    return all_cards


# ── Result-page scraping ────────────────────────────────────────────────────
def scrape_result(context, rb):
    """Visit a single result page and return an entry dict holding the
    structured tender data, or None if the page is not a viewable
    information page."""
    entry = {
        "label": rb["label"],
        "url": rb["url"],
        "data": {},
        "error": "",
    }

    bid_page = context.new_page()
    try:
        bid_page.goto(rb["url"], wait_until="domcontentloaded")
        try:
            bid_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # GeM silently returns the home page (HTTP 200) when a result
        # isn't actually viewable for the given id. Detect and skip.
        title = bid_page.title() or ""
        html_content = bid_page.content()
        page_type = detect_page_type(title)

        print("Page Type:", page_type)
        print("URL:", bid_page.url)
        print("TITLE:", title)

        if page_type != "information":
            print(f"  - {rb['label']}: NOT AN INFORMATION PAGE - SKIPPED")
            return None

        expanded = bid_page.evaluate(EXPAND_PANELS_JS)
        time.sleep(1)  # let any lazy content render

        # Keep only the structured tender info (drops the page-wide
        # header/footer/nav noise that document.body.innerText would carry).
        entry["data"] = extract_bid_data(html_content)
        sections = sum(1 for v in entry["data"].values() if v)
        print(f"  - {rb['label']}: expanded {expanded} extra panel(s), "
              f"{sections} data section(s) captured")
        return entry
    except Exception as e:
        entry["error"] = str(e)
        print(f"  - {rb['label']}: ERROR {e}")
        return entry
    finally:
        try:
            bid_page.close()
        except Exception:
            pass


def scrape_all_results(context, cards):
    """Visit the result pages for every card and attach the scraped entries."""
    print("Visiting result pages...")
    for idx, card in enumerate(cards, start=1):
        bid_no = card["bid_no"] or f"bid_{idx}"
        print(f"[{idx}/{len(cards)}] {bid_no}  ({len(card['result_buttons'])} result link(s))")
        card["results"] = []

        for rb in card["result_buttons"]:
            entry = scrape_result(context, rb)
            if entry is not None:
                card["results"].append(entry)

        if not card["result_buttons"]:
            print("  - no result buttons on card")


def slim_cards(cards):
    """Reduce each card to the fields that matter for a tender, dropping
    redundant/raw scraping artifacts (relative hrefs, the raw result_buttons
    list now superseded by `results`, and the short item teaser)."""
    slim = []
    for c in cards:
        slim.append({
            "bid_no": c.get("bid_no", ""),
            "status": c.get("status", ""),
            "item_category": c.get("items_category", ""),
            "items": c.get("items_full", "") or c.get("items_short", ""),
            "listing": c.get("rows", []),
            "source_page": c.get("source_page"),
            "results": [
                {"label": r["label"], "url": r["url"],
                 "data": r.get("data", {}), "error": r.get("error", "")}
                for r in c.get("results", [])
            ],
        })
    return slim


# ── Orchestration per status ────────────────────────────────────────────────
def collect_status(context, checkbox_id, folder_name, cfg):
    """Run the full pipeline for one Bid/RA status and write its summary.json."""
    out_dir = os.path.join(cfg.results_dir, folder_name)
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n=== {folder_name.upper()} ({checkbox_id}) ===")
    page = open_filtered_search(context, checkbox_id, cfg)
    cards = collect_cards(page, cfg)
    scrape_all_results(context, cards)

    summary_path = os.path.join(out_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(prune_empty(slim_cards(cards)), fh, ensure_ascii=False, indent=2)
    print(f"Saved summary -> {summary_path}")

    page.close()
    return cards


# ── Post-run cleanup ────────────────────────────────────────────────────────
def finalize_summaries(cfg):
    """Keep only the summary.json from each status folder, collect them into a
    folder named after the keyword, and remove the per-bid artifacts."""
    keyword_dir = os.path.join(cfg.results_dir, safe_name(cfg.keyword))
    os.makedirs(keyword_dir, exist_ok=True)

    print(f"\n=== FINALIZING -> {keyword_dir} ===")
    for _checkbox_id, folder in cfg.statuses:
        src = os.path.join(cfg.results_dir, folder, "summary.json")
        if not os.path.exists(src):
            print(f"  {folder}: no summary.json (skipped)")
            continue

        dest = os.path.join(keyword_dir, f"{folder}_summary.json")
        shutil.copyfile(src, dest)
        print(f"  {folder}: summary -> {dest}")

        # Drop the working folder and everything except the collected summary.
        shutil.rmtree(os.path.join(cfg.results_dir, folder), ignore_errors=True)

    return keyword_dir


# ── Entry point ─────────────────────────────────────────────────────────────
def run(cfg=None):
    """Run the full scrape. Pass a Config to override defaults; when omitted,
    the built-in default_config() is used."""
    cfg = cfg or default_config()
    print(f"Config: keyword={cfg.keyword!r}, max_pages={cfg.max_pages}")

    os.makedirs(cfg.download_dir, exist_ok=True)
    os.makedirs(cfg.results_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.headless)
        context = browser.new_context(accept_downloads=True)

        overview = {}
        for checkbox_id, folder in cfg.statuses:
            try:
                cards = collect_status(context, checkbox_id, folder, cfg)
                overview[folder] = len(cards)
            except Exception as e:
                print(f"FAILED {folder}: {e}")
                overview[folder] = f"error: {e}"

        keyword_dir = finalize_summaries(cfg)

        print("\n=== OVERVIEW ===")
        for k, v in overview.items():
            print(f"  {k}: {v}")
        print(f"Summaries saved in: {keyword_dir}")

        print("\nPausing 5s before closing browser...")
        time.sleep(5)
        browser.close()


def parse_args(argv=None):
    """Build a Config from command-line args, falling back to defaults."""
    defaults = default_config()
    parser = argparse.ArgumentParser(
        description="Scrape GeM BidPlus result pages for a keyword."
    )
    parser.add_argument(
        "-k", "--keyword", default=defaults.keyword,
        help=f"Search keyword (default: {defaults.keyword!r})",
    )
    parser.add_argument(
        "-p", "--max-pages", type=int, default=defaults.max_pages,
        help=f"Max result pages per status; 0 disables the cap "
             f"(default: {defaults.max_pages})",
    )
    parser.add_argument(
        "--headless", action="store_true", default=defaults.headless,
        help="Run the browser headless.",
    )
    args = parser.parse_args(argv)
    return Config(
        keyword=args.keyword,
        max_pages=args.max_pages or None,  # treat 0 as "no cap"
        headless=args.headless,
    )


if __name__ == "__main__":
    run(parse_args())
