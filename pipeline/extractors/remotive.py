"""Remotive public API extractor.

Endpoint: GET https://remotive.com/api/remote-jobs
Response shape::

    { "job-count": N, "jobs": [ { "id", "url", "title", "company_name",
      "category", "tags": [...], "job_type", "publication_date",
      "candidate_required_location", "salary", "description" }, ... ] }
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from pipeline.config import HEADERS, REMOTIVE_URL, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


def extract() -> list[dict[str, Any]]:
    """Return raw job records from the Remotive API."""
    logger.info("Remotive: starting extraction")
    response = requests.get(
        REMOTIVE_URL,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    jobs: list[dict[str, Any]] = response.json().get("jobs", [])
    logger.info("Remotive: fetched %d records", len(jobs))
    return jobs
