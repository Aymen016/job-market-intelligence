"""We Work Remotely HTML scraper.

WWR publishes no public JSON API, so we GET the main listing page and
extract job cards with BeautifulSoup.

WWR groups jobs by category inside ``<section class="jobs">`` blocks.
Each job is an ``<li>`` element; the first ``<li>`` in each section is
a header/divider row that we skip by checking for known CSS classes.
"""
from __future__ import annotations

import logging
from typing import Any

import requests
from bs4 import BeautifulSoup

from pipeline.config import HEADERS, REQUEST_TIMEOUT, WWR_BASE_URL, WWR_URL

logger = logging.getLogger(__name__)

# CSS classes that mark non-job rows (headers, "view all" links, dividers)
_SKIP_CLASSES = frozenset({"view-all", "region-label", "hed"})


def extract() -> list[dict[str, Any]]:
    """Scrape job listings from We Work Remotely's public HTML page."""
    logger.info("WeWorkRemotely: starting scrape of %s", WWR_URL)
    response = requests.get(WWR_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    jobs: list[dict[str, Any]] = []

    for section in soup.select("section.jobs"):
        # Derive category name from the section heading
        heading = section.find("h2")
        category = heading.get_text(strip=True) if heading else "Other"

        for li in section.select("li"):
            # Skip header / divider / "View All" rows
            row_classes = set(li.get("class", []))
            if row_classes & _SKIP_CLASSES:
                continue

            link_el = li.select_one("a[href]")
            if not link_el:
                continue

            href: str = link_el.get("href", "")
            url = f"{WWR_BASE_URL}{href}" if href.startswith("/") else href

            title_el   = li.select_one(".title")
            company_el = li.select_one(".company")
            region_el  = li.select_one(".region, .flag-flag")

            title   = title_el.get_text(strip=True)   if title_el   else ""
            company = company_el.get_text(strip=True)  if company_el else ""
            region  = region_el.get_text(strip=True)   if region_el  else "Worldwide"

            if not title:
                continue  # malformed row — skip silently

            jobs.append(
                {
                    "title":       title,
                    "company":     company,
                    "location":    region,
                    "category":    category,
                    "url":         url,
                    "tags":        [],
                    "description": "",
                    "salary":      "",
                }
            )

    logger.info("WeWorkRemotely: scraped %d records", len(jobs))
    return jobs
