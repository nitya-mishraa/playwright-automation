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
MAX_PAGES = None  # safety ceiling – set to None to disable

# (checkbox id on the page, output subfolder name)
STATUSES = [
    ("bid_awarded", "awarded"),
    ("tech_evaluated", "technical"),
    ("fin_evaluated", "financial"),
]


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")

def extract_bid_data(html):
    from bs4 import BeautifulSoup
    import re

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    data = {
        "bid_details": {},
        "buyer_details": {},
        "technical_evaluation": [],
    "financial_evaluation": []
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
                    data["technical_evaluation"].append({"sr_no": cols[0],
                        "seller_name": cols[1],
                        "offered_item": cols[2],
                        "participated_on": cols[3],
                        "mse_mii_status": cols[4],
                        "status": cols[5]
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
                        "rank": cols[4]
                    })

    return data

def detect_page_type(title):
    title = title.lower()

    if "national public procurement portal" in title:
        return "homepage"

    if "gem" in title and "bidding" in title:
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
    time.sleep(3)

    

   

    # ── Paginated card extraction ──────────────────────────────────────────────
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

        # Stop if no cards came back (empty page) or we hit the safety ceiling
        if not batch:
            print("  Empty page – stopping pagination.")
            break
        if MAX_PAGES and page_num >= MAX_PAGES:
            print(f"  Reached MAX_PAGES={MAX_PAGES} – stopping pagination.")
            break

        has_next = page.evaluate(PAGINATION_HAS_NEXT_JS)
        if not has_next:
            print("  No further pages detected.")
            break

        print("  Navigating to next page...")

       

        clicked = page.evaluate(PAGINATION_CLICK_NEXT_JS)

        if not clicked:
            break

        

        time.sleep(2)
        page_num += 1

    cards = all_cards
    print(f"Total bid cards collected across {page_num} page(s): {len(cards)}")
    # ── End pagination ─────────────────────────────────────────────────────────

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

                page_type = detect_page_type(title)

                print("Page Type:", page_type)
                print("URL:", bid_page.url)
                print("TITLE:", bid_page.title())
                
                if page_type != "information":
                    print(f"  - {rb['label']}: NOT AN INFORMATION PAGE - SKIPPED")
                    bid_page.close()
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
                    fh.write(html_content)

                data = extract_bid_data(html_content)

                json_path = os.path.join(out_dir, f"{slug}_data.json")

                with open(json_path, "w", encoding="utf-8") as jf:
                    json.dump(data, jf, indent=2)
                    

                #png_path = os.path.join(out_dir, f"{slug}.png")
                #bid_page.screenshot(path=png_path, full_page=True)

                entry["text"] = bid_page.evaluate("() => document.body.innerText")
                entry["html_file"] = html_path
                entry["screenshot"] = ""
                entry["panels_expanded"] = expanded
                print(f"  - {rb['label']}: expanded {expanded} extra panel(s), saved ({len(entry['text'])} chars)")
                bid_page.close()
            except Exception as e:
                entry["error"] = str(e)
                print(f"  - {rb['label']}: ERROR {e}")
                try:
                    bid_page.close()
                except:
                    pass

                continue
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