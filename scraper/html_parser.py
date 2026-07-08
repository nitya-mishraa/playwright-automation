"""Helpers for turning raw scraped HTML into structured tender data."""

import re

from bs4 import BeautifulSoup


def safe_name(s):
    """Sanitize a string for use as a filesystem path segment."""
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
    """Resolve a possibly-relative GeM BidPlus href into an absolute URL."""
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if not href.startswith("/"):
        href = "/" + href
    return f"https://bidplus.gem.gov.in{href}"


def detect_page_type(title):
    """Classify a result page from its <title> so home-page bounces can be skipped."""
    title = title.lower()
    if "national public procurement portal" in title:
        return "homepage"
    if "gem" in title and "bidding" in title:
        return "information"
    return "unknown"


def extract_bid_data(html):
    """Parse a bid's information page HTML into bid/buyer details and
    technical/financial evaluation tables."""
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
