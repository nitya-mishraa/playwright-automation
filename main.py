#!/usr/bin/env python3
"""Entry point for the GeM BidPlus tender scraper.

Usage:
    python main.py -k Intelligence
    python main.py -k Drone -p 0 --headless
"""

import logging

from scraper.config import parse_args
from scraper.pipeline import run

logging.basicConfig(level=logging.INFO, format="%(message)s")

if __name__ == "__main__":
    run(parse_args())
