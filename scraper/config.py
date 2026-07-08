"""Runtime configuration and CLI argument parsing for the scraper."""

import argparse
from dataclasses import dataclass, field


@dataclass
class Config:
    """Runtime configuration for a scraping run.

    Construct with overrides (e.g. ``Config(keyword="Drone", max_pages=5)``)
    or call :func:`default_config` for the built-in defaults.
    """
    keyword: str = "Intelligence"
    max_pages: int | None = 3  # safety ceiling - set to None to disable
    base_url: str = "https://bidplus.gem.gov.in/all-bids"
    results_dir: str = "./results"
    bid_type_checkbox: str = "service"  # "Service Bid/RAs" checkbox id on the page
    headless: bool = False
    # (checkbox id on the page, output subfolder name)
    statuses: list[tuple[str, str]] = field(default_factory=lambda: [
        ("bid_awarded", "awarded"),
        ("tech_evaluated", "technical"),
        ("fin_evaluated", "financial"),
    ])


def default_config() -> Config:
    """Return a Config populated entirely with built-in defaults."""
    return Config()


def parse_args(argv=None) -> Config:
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
