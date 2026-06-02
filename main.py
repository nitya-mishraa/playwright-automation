from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import os
import re
import time

KEYWORD = "intelligence"
BASE_URL = "https://bidplus.gem.gov.in/all-bids"
DOWNLOAD_DIR = "./downloads"
RESULTS_DIR = "./results"

# (checkbox id on the page, output subfolder name)
STATUSES = [
    ("bid_awarded", "awarded"),
    ("tech_evaluated", "technical"),
    ("fin_evaluated", "financial"),
]


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")

def extract_bid_data(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    return {
        "has_bid_details": "bid details" in text.lower(),
        "has_technical_evaluation": "technical evaluation" in text.lower(),
        "has_financial_evaluation": "financial evaluation" in text.lower()
    }

def detect_page_type(html):
    html = html.lower()

    if "national public procurement portal" in html:
        return "homepage"
    

    if "technical evaluation" in html:
        return "information"

    if "financial evaluation" in html:
        return "information"

    if "bid details" in html:
        return "information"

    return "unknown"
def absolutize(href):
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if not href.startswith("/"):
        href = "/" + href
    return f"https://bidplus.gem.gov.in{href}"


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


def collect_status(context, checkbox_id, folder_name):
    """Open a fresh page, switch to Bid/RA Status tab, tick `checkbox_id`,
    search KEYWORD, then visit every result page and save html/screenshot/text."""
    out_dir = os.path.join(RESULTS_DIR, folder_name)
    os.makedirs(out_dir, exist_ok=True)

    page = context.new_page()
    print(f"\n=== {folder_name.upper()} ({checkbox_id}) ===")
    print("Opening GeM BidPlus...")
    page.goto(BASE_URL, wait_until="networkidle")

    print("Switching to Bid/RA Status tab...")
    page.evaluate("document.getElementById('bidrastatus').click()")
    time.sleep(1)

    print(f"Ticking {checkbox_id}...")
    page.evaluate(f"document.getElementById('{checkbox_id}').click()")
    time.sleep(2)

    print(f"Searching keyword: {KEYWORD}")
    search_input = page.locator("#searchBid")
    search_input.fill(KEYWORD)
    search_input.press("Enter")
    page.wait_for_load_state("networkidle")
    time.sleep(5)

    print("Extracting bid card metadata...")
    cards = page.evaluate(CARD_EXTRACT_JS)
    print(f"Found {len(cards)} bid cards")

    for c in cards:
        for bl in c["bid_links"]:
            bl["url"] = absolutize(bl["href"])
        for rb in c["result_buttons"]:
            rb["url"] = absolutize(rb["href"])
        c["bid_no"] = c["bid_links"][0]["text"] if c["bid_links"] else ""

    print("Visiting result pages...")
    for idx, card in enumerate(cards, start=1):
        bid_no = card["bid_no"] or f"bid_{idx}"
        print(f"[{idx}/{len(cards)}] {bid_no}  ({len(card['result_buttons'])} result link(s))")
        card["results"] = []

        for rb_idx, rb in enumerate(card["result_buttons"], start=1):
            entry = {
                "label": rb["label"],
                "url": rb["url"],
                "html_file": "",
                "screenshot": "",
                "text": "",
                "error": "",
            }
            slug = safe_name(f"{bid_no}_{rb['label']}") or f"bid_{idx}_{rb_idx}"
            try:
                bid_page = context.new_page()
                response = bid_page.goto(rb["url"], wait_until="domcontentloaded")
                try:
                    bid_page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

                # GeM silently returns the home page (HTTP 200) when a result
                # isn't actually viewable for the given id. Detect and skip.
                final_url = bid_page.url
                title = bid_page.title() or ""
                html_content = bid_page.content()

                page_type = detect_page_type(html_content)

                print("Page Type:", page_type)
                is_home = (page_type == "homepage")
                if is_home:
                    
                    status_code = response.status if response else "?"
                    entry["error"] = (
                        f"redirected_to_home (status={status_code}, final_url={final_url})"
                    )
                    print(f"  - {rb['label']}: REDIRECTED to home — result not published for this id")
                    bid_page.close()
                    card["results"].append(entry)
                    continue

                # Force-open every Bootstrap collapse panel on the page so all
                # sections render before we capture HTML/text/screenshot.
                expanded = bid_page.evaluate(
                    """() => {
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
                )
                time.sleep(1)  # let any lazy content render

                html_path = os.path.join(out_dir, f"{slug}.html")
                with open(html_path, "w", encoding="utf-8") as fh:
                    fh.write(bid_page.content())

                data = extract_bid_data(html_content)

                json_path = os.path.join(out_dir, f"{slug}_data.json")

                with open(json_path, "w", encoding="utf-8") as jf:
                    json.dump(data, jf, indent=2)
                    

                png_path = os.path.join(out_dir, f"{slug}.png")
                bid_page.screenshot(path=png_path, full_page=True)

                entry["text"] = bid_page.evaluate("() => document.body.innerText")
                entry["html_file"] = html_path
                entry["screenshot"] = png_path
                entry["panels_expanded"] = expanded
                print(f"  - {rb['label']}: expanded {expanded} extra panel(s), saved ({len(entry['text'])} chars)")
                bid_page.close()
            except Exception as e:
                entry["error"] = str(e)
                print(f"  - {rb['label']}: ERROR {e}")

            card["results"].append(entry)

        if not card["result_buttons"]:
            print("  - no result buttons on card")

    summary_path = os.path.join(out_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(cards, fh, ensure_ascii=False, indent=2)
    print(f"Saved summary -> {summary_path}")

    page.close()
    return cards


os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(accept_downloads=True)

    overview = {}
    for checkbox_id, folder in STATUSES:
        try:
            cards = collect_status(context, checkbox_id, folder)
            overview[folder] = len(cards)
        except Exception as e:
            print(f"FAILED {folder}: {e}")
            overview[folder] = f"error: {e}"

    print("\n=== OVERVIEW ===")
    for k, v in overview.items():
        print(f"  {k}: {v}")

    print("\nPausing 5s before closing browser...")
    time.sleep(5)
    browser.close()