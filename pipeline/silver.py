"""Silver layer — clean, unify, and de-duplicate across all bronze sources.

DuckDB reads every raw Parquet file directly (no server required).
The output is a single ``data/silver/jobs.parquet`` rebuilt on every run.

Transformations applied here
----------------------------
* **Schema normalisation** — map each source's field names to a shared schema:
  ``url, title, company, location, remote, salary, posted_date, category,
  source, description, tags``
* **HTML stripping** — Arbeitnow descriptions arrive as HTML; plain text is
  extracted with BeautifulSoup.
* **De-duplication** — jobs with the same normalised URL are collapsed to one
  row (the first occurrence across sources wins).
* **Skill extraction** — each posting is tagged with every skill keyword from
  ``config.SKILLS`` that appears in its description or tags.
"""
from __future__ import annotations

import logging
import re
from datetime import date

import duckdb
import pandas as pd
from bs4 import BeautifulSoup

from pipeline.config import BRONZE_DIR, SILVER_DIR, SKILLS

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_html(html: str | None) -> str:
    """Remove HTML markup and return plain text."""
    if not html:
        return ""
    return BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)


def _extract_skills(description: str | None, tags: object) -> list[str]:
    """Return all matching skill keywords found in *description* + *tags*."""
    tag_text = " ".join(tags) if isinstance(tags, list) else ""
    haystack = f"{(description or '').lower()} {tag_text.lower()}"
    return sorted(
        {skill for skill in SKILLS if re.search(rf"\b{re.escape(skill)}\b", haystack)}
    )


def _parquet_glob(source: str) -> str:
    """
    Return a DuckDB-compatible glob for all Parquet files under *source*.
    Returns an empty string when no files exist yet (avoids DuckDB errors).
    """
    base = BRONZE_DIR / f"source={source}"
    if not base.exists() or not any(base.glob("**/*.parquet")):
        return ""
    # DuckDB requires forward slashes even on Windows
    return base.as_posix() + "/**/*.parquet"


# ── Per-source normalizers ────────────────────────────────────────────────────

def _read_remotive(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    glob = _parquet_glob("remotive")
    if not glob:
        logger.warning("Silver: no Remotive bronze files found — skipping")
        return pd.DataFrame()

    conn.execute(
        f"CREATE OR REPLACE VIEW _remotive AS SELECT * FROM read_parquet('{glob}')"
    )
    return conn.execute("""
        SELECT
            url,
            title,
            company_name                                          AS company,
            COALESCE(candidate_required_location, 'Worldwide')    AS location,
            true                                                  AS remote,
            COALESCE(salary, '')                                  AS salary,
            TRY_CAST(SUBSTRING(publication_date, 1, 10) AS DATE)  AS posted_date,
            COALESCE(category, '')                                AS category,
            'remotive'                                            AS source,
            COALESCE(description, '')                             AS description,
            COALESCE(tags, [])                                    AS tags
        FROM _remotive
        WHERE url IS NOT NULL AND title IS NOT NULL AND title <> ''
    """).df()


def _read_arbeitnow(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    glob = _parquet_glob("arbeitnow")
    if not glob:
        logger.warning("Silver: no Arbeitnow bronze files found — skipping")
        return pd.DataFrame()

    conn.execute(
        f"CREATE OR REPLACE VIEW _arbeitnow AS SELECT * FROM read_parquet('{glob}')"
    )
    return conn.execute("""
        SELECT
            url,
            title,
            company_name                                                      AS company,
            COALESCE(location, 'Worldwide')                                   AS location,
            COALESCE(remote, false)                                           AS remote,
            ''                                                                AS salary,
            TRY_CAST(epoch_ms(TRY_CAST(created_at AS BIGINT) * 1000) AS DATE) AS posted_date,
            COALESCE(
                CASE WHEN array_length(job_types) > 0 THEN job_types[1] ELSE '' END,
                ''
            )                                                                 AS category,
            'arbeitnow'                                                       AS source,
            COALESCE(description, '')                                         AS description,
            COALESCE(tags, [])                                                AS tags
        FROM _arbeitnow
        WHERE url IS NOT NULL AND title IS NOT NULL AND title <> ''
    """).df()


def _read_wwr(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    glob = _parquet_glob("weworkremotely")
    if not glob:
        logger.warning("Silver: no WeWorkRemotely bronze files found — skipping")
        return pd.DataFrame()

    today = str(date.today())
    conn.execute(
        f"CREATE OR REPLACE VIEW _wwr AS SELECT * FROM read_parquet('{glob}')"
    )
    return conn.execute(f"""
        SELECT
            url,
            title,
            COALESCE(company, '')           AS company,
            COALESCE(location, 'Worldwide') AS location,
            true                            AS remote,
            COALESCE(salary, '')            AS salary,
            CAST('{today}' AS DATE)         AS posted_date,
            COALESCE(category, '')          AS category,
            'weworkremotely'                AS source,
            COALESCE(description, '')       AS description,
            COALESCE(tags, [])              AS tags
        FROM _wwr
        WHERE url IS NOT NULL AND title IS NOT NULL AND title <> ''
    """).df()


# ── Main transform ────────────────────────────────────────────────────────────

def transform() -> int:
    """
    Rebuild ``data/silver/jobs.parquet`` from all available bronze data.

    Returns the number of deduplicated records written.
    """
    logger.info("Silver: starting transformation")
    conn = duckdb.connect()

    frames = [
        _read_remotive(conn),
        _read_arbeitnow(conn),
        _read_wwr(conn),
    ]
    combined = pd.concat(
        [f for f in frames if not f.empty], ignore_index=True
    )

    if combined.empty:
        logger.warning("Silver: no source data available — nothing written")
        return 0

    # Strip HTML from descriptions (primarily Arbeitnow)
    combined["description"] = combined["description"].apply(_strip_html)

    # Normalise URL as the deduplication key
    combined["url"] = combined["url"].str.strip().str.lower()
    combined.drop_duplicates(subset=["url"], keep="first", inplace=True)

    # Extract skills from description + tags
    combined["skills"] = combined.apply(
        lambda row: _extract_skills(row["description"], row["tags"]),
        axis=1,
    )

    # Record when this snapshot was built
    combined["ingest_date"] = date.today()

    out_path = SILVER_DIR / "jobs.parquet"
    combined.to_parquet(out_path, index=False, engine="pyarrow")

    count = len(combined)
    logger.info("Silver: wrote %d deduplicated records → %s", count, out_path)
    return count
