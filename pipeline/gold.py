"""Gold layer — analytical mart tables aggregated from the silver dataset.

DuckDB reads ``data/silver/jobs.parquet`` directly and writes each mart
as a small Parquet file under ``data/gold/``.  All tables are rebuilt
(full-refresh) on every pipeline run.

Mart tables produced
--------------------
``skill_demand``
    Per-skill job count and share of total; answers "which skills are most
    in demand?"

``remote_split``
    Remote vs on-site count and percentage.

``top_categories``
    Job count by category (top 30).

``salary_samples``
    Raw salary strings where disclosed, grouped by source — useful for
    manual review since salary formats vary widely across boards.

``daily_volume``
    Posting count per source per ingest date — the building block for
    trend charts once multiple days accumulate.

``skill_cooccurrence``
    Top 50 skill pairs that appear together most often — reveals which
    technologies are bundled in practice (e.g. Spark + Python + AWS).
"""
from __future__ import annotations

import logging

import duckdb

from pipeline.config import GOLD_DIR, SILVER_DIR

logger = logging.getLogger(__name__)

_SILVER = str(SILVER_DIR / "jobs.parquet")


def _write(conn: duckdb.DuckDBPyConnection, sql: str, name: str) -> int:
    """Execute *sql* and write the result to ``data/gold/{name}.parquet``."""
    out = (GOLD_DIR / f"{name}.parquet").as_posix()
    conn.execute(f"COPY ({sql}) TO '{out}' (FORMAT PARQUET, OVERWRITE_OR_IGNORE TRUE)")
    count: int = conn.execute(
        f"SELECT COUNT(*) FROM read_parquet('{out}')"
    ).fetchone()[0]
    logger.info("Gold %-25s → %d rows", name, count)
    return count


def aggregate() -> None:
    """Compute and persist all gold mart tables from ``silver/jobs.parquet``."""
    logger.info("Gold: starting aggregation")
    conn = duckdb.connect()
    conn.execute(
        f"CREATE OR REPLACE VIEW silver AS SELECT * FROM read_parquet('{_SILVER}')"
    )

    # ── 1. Skill demand ───────────────────────────────────────────────────────
    _write(conn, """
        SELECT
            skill,
            COUNT(*)                                                AS job_count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2)     AS pct_of_total
        FROM silver, UNNEST(skills) AS t(skill)
        GROUP BY skill
        ORDER BY job_count DESC
    """, "skill_demand")

    # ── 2. Remote vs on-site ──────────────────────────────────────────────────
    _write(conn, """
        SELECT
            CASE WHEN remote THEN 'Remote' ELSE 'On-site' END       AS work_type,
            COUNT(*)                                                 AS job_count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1)      AS pct
        FROM silver
        GROUP BY remote
        ORDER BY job_count DESC
    """, "remote_split")

    # ── 3. Top categories ─────────────────────────────────────────────────────
    _write(conn, """
        SELECT
            category,
            COUNT(*) AS job_count
        FROM silver
        WHERE category IS NOT NULL AND category <> ''
        GROUP BY category
        ORDER BY job_count DESC
        LIMIT 30
    """, "top_categories")

    # ── 4. Salary samples (where disclosed) ───────────────────────────────────
    _write(conn, """
        SELECT
            source,
            salary,
            COUNT(*) AS count
        FROM silver
        WHERE salary IS NOT NULL AND salary <> ''
        GROUP BY source, salary
        ORDER BY count DESC
        LIMIT 200
    """, "salary_samples")

    # ── 5. Daily posting volume (trend foundation) ────────────────────────────
    _write(conn, """
        SELECT
            ingest_date,
            source,
            COUNT(*) AS job_count
        FROM silver
        GROUP BY ingest_date, source
        ORDER BY ingest_date, source
    """, "daily_volume")

    # ── 6. Skill co-occurrence (top 50 pairs) ─────────────────────────────────
    _write(conn, """
        SELECT
            a.skill  AS skill_a,
            b.skill  AS skill_b,
            COUNT(*) AS co_occurrences
        FROM silver,
             UNNEST(skills) AS a(skill),
             UNNEST(skills) AS b(skill)
        WHERE a.skill < b.skill
        GROUP BY skill_a, skill_b
        ORDER BY co_occurrences DESC
        LIMIT 50
    """, "skill_cooccurrence")

    logger.info("Gold: all mart tables refreshed")
