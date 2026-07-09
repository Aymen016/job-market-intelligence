"""Arbeitnow public API extractor — paginated.

Endpoint: GET https://www.arbeitnow.com/api/job-board-api?page=N
Response shape::

    { "data": [ { "slug", "company_name", "title", "description",
      "remote": bool, "tags": [...], "job_types": [...],
      "location", "created_at": unix_ts, "url" }, ... ],
      "links": { "next": url | null }, "meta": {...} }

The extractor walks pages until "next" is null or _MAX_PAGES is reached.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from pipeline.config import ARBEITNOW_URL, HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

_MAX_PAGES = 5  # ~100 jobs/page; stay respectful


def extract() -> list[dict[str, Any]]:
    """Return raw job records from Arbeitnow, walking all available pages."""
    logger.info("Arbeitnow: starting extraction")
    records: list[dict[str, Any]] = []
    next_url: str | None = ARBEITNOW_URL

    for page in range(1, _MAX_PAGES + 1):
        if next_url is None:
            break
        response = requests.get(next_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        batch: list[dict[str, Any]] = payload.get("data", [])
        if not batch:
            break
        records.extend(batch)
        logger.debug("Arbeitnow: page %d → %d records", page, len(batch))
        next_url = payload.get("links", {}).get("next")

    logger.info("Arbeitnow: fetched %d records total", len(records))
    return records
