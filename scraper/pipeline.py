"""Scraping pipeline: filter/search, paginate, scrape result pages, and
persist per-status summaries."""

import json
import logging
import os
import shutil
import time

from playwright.sync_api import sync_playwright

from .browser_scripts import (
    CARD_EXTRACT_JS,
    EXPAND_PANELS_JS,
    PAGINATION_CLICK_NEXT_JS,
    PAGINATION_HAS_NEXT_JS,
    PAGINATION_INFO_JS,
)
from .config import default_config
from .html_parser import absolutize, detect_page_type, extract_bid_data, prune_empty, safe_name

logger = logging.getLogger(__name__)


# ── Search / filtering ──────────────────────────────────────────────────────
def open_filtered_search(context, checkbox_id, cfg):
    """Open a fresh page, apply Bid/RA status + Service bid-type filters,
    search cfg.keyword and wait for results."""
    page = context.new_page()
    logger.info("Opening GeM BidPlus...")
    page.goto(cfg.base_url, wait_until="networkidle")

    logger.info("Switching to Bid/RA Status tab...")
    page.evaluate("document.getElementById('bidrastatus').click()")
    time.sleep(1)

    logger.info("Ticking %s...", checkbox_id)
    page.evaluate(f"document.getElementById('{checkbox_id}').click()")
    time.sleep(2)

    logger.info("Selecting Bid Type: Service Bid/RAs...")
    page.evaluate(f"document.getElementById('{cfg.bid_type_checkbox}').click()")
    time.sleep(2)

    logger.info("Searching keyword: %s", cfg.keyword)
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
        logger.info(page.locator("#light-pagination").inner_text())
        pg_info = page.evaluate(PAGINATION_INFO_JS)
        total_label = f"/{pg_info['total']}" if pg_info["total"] else ""
        logger.info("Extracting bid cards - page %s%s ...", page_num, total_label)

        batch = page.evaluate(CARD_EXTRACT_JS)
        logger.info("  %d card(s) on this page", len(batch))

        for c in batch:
            for bl in c["bid_links"]:
                bl["url"] = absolutize(bl["href"])
            for rb in c["result_buttons"]:
                rb["url"] = absolutize(rb["href"])
            c["bid_no"] = c["bid_links"][0]["text"] if c["bid_links"] else ""
            c["source_page"] = page_num

        all_cards.extend(batch)

        if not batch:
            logger.info("  Empty page - stopping pagination.")
            break
        if cfg.max_pages and page_num >= cfg.max_pages:
            logger.info("  Reached max_pages=%s - stopping pagination.", cfg.max_pages)
            break

        if not page.evaluate(PAGINATION_HAS_NEXT_JS):
            logger.info("  No further pages detected.")
            break

        logger.info("  Navigating to next page...")
        if not page.evaluate(PAGINATION_CLICK_NEXT_JS):
            break

        time.sleep(2)
        page_num += 1

    logger.info("Total bid cards collected across %d page(s): %d", page_num, len(all_cards))
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

        logger.info("Page Type: %s", page_type)
        logger.info("URL: %s", bid_page.url)
        logger.info("TITLE: %s", title)

        if page_type != "information":
            logger.info("  - %s: NOT AN INFORMATION PAGE - SKIPPED", rb["label"])
            return None

        expanded = bid_page.evaluate(EXPAND_PANELS_JS)
        time.sleep(1)  # let any lazy content render

        # Keep only the structured tender info (drops the page-wide
        # header/footer/nav noise that document.body.innerText would carry).
        entry["data"] = extract_bid_data(html_content)
        sections = sum(1 for v in entry["data"].values() if v)
        logger.info(
            "  - %s: expanded %d extra panel(s), %d data section(s) captured",
            rb["label"], expanded, sections,
        )
        return entry
    except Exception as e:
        entry["error"] = str(e)
        logger.warning("  - %s: ERROR %s", rb["label"], e)
        return entry
    finally:
        try:
            bid_page.close()
        except Exception:
            pass


def scrape_all_results(context, cards):
    """Visit the result pages for every card and attach the scraped entries."""
    logger.info("Visiting result pages...")
    for idx, card in enumerate(cards, start=1):
        bid_no = card["bid_no"] or f"bid_{idx}"
        logger.info("[%d/%d] %s  (%d result link(s))", idx, len(cards), bid_no, len(card["result_buttons"]))
        card["results"] = []

        for rb in card["result_buttons"]:
            entry = scrape_result(context, rb)
            if entry is not None:
                card["results"].append(entry)

        if not card["result_buttons"]:
            logger.info("  - no result buttons on card")


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

    logger.info("=== %s (%s) ===", folder_name.upper(), checkbox_id)
    page = open_filtered_search(context, checkbox_id, cfg)
    cards = collect_cards(page, cfg)
    scrape_all_results(context, cards)

    summary_path = os.path.join(out_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(prune_empty(slim_cards(cards)), fh, ensure_ascii=False, indent=2)
    logger.info("Saved summary -> %s", summary_path)

    page.close()
    return cards


# ── Post-run cleanup ────────────────────────────────────────────────────────
def finalize_summaries(cfg):
    """Keep only the summary.json from each status folder, collect them into a
    folder named after the keyword, and remove the per-bid artifacts."""
    keyword_dir = os.path.join(cfg.results_dir, safe_name(cfg.keyword))
    os.makedirs(keyword_dir, exist_ok=True)

    logger.info("=== FINALIZING -> %s ===", keyword_dir)
    for _checkbox_id, folder in cfg.statuses:
        src = os.path.join(cfg.results_dir, folder, "summary.json")
        if not os.path.exists(src):
            logger.info("  %s: no summary.json (skipped)", folder)
            continue

        dest = os.path.join(keyword_dir, f"{folder}_summary.json")
        shutil.copyfile(src, dest)
        logger.info("  %s: summary -> %s", folder, dest)

        # Drop the working folder and everything except the collected summary.
        shutil.rmtree(os.path.join(cfg.results_dir, folder), ignore_errors=True)

    return keyword_dir


# ── Entry point ─────────────────────────────────────────────────────────────
def run(cfg=None):
    """Run the full scrape. Pass a Config to override defaults; when omitted,
    the built-in default_config() is used."""
    cfg = cfg or default_config()
    logger.info("Config: keyword=%r, max_pages=%s", cfg.keyword, cfg.max_pages)

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
                logger.error("FAILED %s: %s", folder, e)
                overview[folder] = f"error: {e}"

        keyword_dir = finalize_summaries(cfg)

        logger.info("=== OVERVIEW ===")
        for k, v in overview.items():
            logger.info("  %s: %s", k, v)
        logger.info("Summaries saved in: %s", keyword_dir)

        logger.info("Pausing 5s before closing browser...")
        time.sleep(5)
        browser.close()
