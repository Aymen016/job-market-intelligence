"""Prefect flow — daily job-market observatory pipeline.

Usage
-----
Run once (no server needed)::

    python flows/daily_flow.py

Run on a repeating 08:00 UTC schedule (keeps the process alive)::

    python flows/daily_flow.py --serve

Pipeline stages
---------------
Stage 1 — Extract (parallel)
    Three tasks run concurrently: Remotive API, Arbeitnow API,
    WeWorkRemotely HTML scrape.  Each has 3 automatic retries with a
    60-second back-off so transient HTTP errors don't abort the run.

Stage 2 — Bronze (parallel)
    Each extractor's records are landed as raw Parquet files immediately
    after that extractor finishes — no waiting for the other sources.

Stage 3 — Silver (sequential)
    Waits for all three bronze tasks, then normalises, deduplicates, and
    extracts skills into a unified ``data/silver/jobs.parquet``.

Stage 4 — Gold (sequential)
    Waits for silver, then rebuilds all analytical mart tables under
    ``data/gold/``.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

from prefect import flow, task
from prefect.logging import get_run_logger

from pipeline.bronze import write as bronze_write
from pipeline.extractors import arbeitnow, remotive, weworkremotely
from pipeline.gold import aggregate as gold_aggregate
from pipeline.silver import transform as silver_transform

logging.basicConfig(level=logging.INFO)


# ── Tasks ─────────────────────────────────────────────────────────────────────

@task(name="extract-remotive", retries=3, retry_delay_seconds=60)
def task_extract_remotive() -> list[dict[str, Any]]:
    logger = get_run_logger()
    records = remotive.extract()
    logger.info("Remotive: %d records", len(records))
    return records


@task(name="extract-arbeitnow", retries=3, retry_delay_seconds=60)
def task_extract_arbeitnow() -> list[dict[str, Any]]:
    logger = get_run_logger()
    records = arbeitnow.extract()
    logger.info("Arbeitnow: %d records", len(records))
    return records


@task(name="extract-weworkremotely", retries=3, retry_delay_seconds=60)
def task_extract_weworkremotely() -> list[dict[str, Any]]:
    logger = get_run_logger()
    records = weworkremotely.extract()
    logger.info("WeWorkRemotely: %d records", len(records))
    return records


@task(name="bronze-land")
def task_bronze(source: str, records: list[dict[str, Any]]) -> str:
    logger = get_run_logger()
    if not records:
        logger.warning("Bronze: no records for source=%s — skipping", source)
        return ""
    path = bronze_write(source, records)
    logger.info("Bronze %-20s → %d records → %s", source, len(records), path)
    return path


@task(name="silver-transform")
def task_silver() -> int:
    logger = get_run_logger()
    count = silver_transform()
    logger.info("Silver: %d deduplicated records written", count)
    return count


@task(name="gold-aggregate")
def task_gold() -> None:
    logger = get_run_logger()
    gold_aggregate()
    logger.info("Gold: mart tables refreshed")


# ── Flow ──────────────────────────────────────────────────────────────────────

@flow(name="daily-job-pipeline", log_prints=True)
def daily_job_pipeline() -> None:
    """
    Extract → Bronze → Silver → Gold.

    Prefect resolves PrefectFutures passed as task arguments automatically,
    so ``task_bronze.submit("remotive", r)`` will wait for extractor future
    ``r`` to complete and forward its result value.
    """
    # ── Stage 1: Extract (all three run in parallel) ──────────────────────────
    r = task_extract_remotive.submit()
    a = task_extract_arbeitnow.submit()
    w = task_extract_weworkremotely.submit()

    # ── Stage 2: Bronze (each lands as soon as its extractor finishes) ────────
    b_r = task_bronze.submit("remotive",       r)
    b_a = task_bronze.submit("arbeitnow",      a)
    b_w = task_bronze.submit("weworkremotely", w)

    # ── Stage 3: Silver (waits for all bronze to finish) ─────────────────────
    s = task_silver.submit(wait_for=[b_r, b_a, b_w])

    # ── Stage 4: Gold (waits for silver) ─────────────────────────────────────
    g = task_gold.submit(wait_for=[s])

    # Block until the whole chain resolves — otherwise Prefect cancels any
    # task runs still in flight the instant this flow function returns.
    g.result()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--serve" in sys.argv:
        # Keep the process alive and run the flow on a daily schedule at 08:00 UTC.
        daily_job_pipeline.serve(
            name="daily-job-pipeline-deployment",
            cron="0 8 * * *",
        )
    else:
        daily_job_pipeline()
