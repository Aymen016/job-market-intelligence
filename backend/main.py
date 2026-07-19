"""FastAPI backend for the Job Market Observatory dashboard.

Reads directly from the gold and silver Parquet files with DuckDB — no
database, no ORM, no separate copy of the data. Each request opens a fresh
in-memory DuckDB connection and reads the Parquet files straight off disk,
which is fast enough for this dataset size (hundreds to low thousands of
rows) and always reflects the latest pipeline run without a restart.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

DATA_DIR = Path(__file__).parent.parent / "data"
SILVER_PATH = DATA_DIR / "silver" / "jobs.parquet"
GOLD_DIR = DATA_DIR / "gold"

app = FastAPI(title="Job Market Observatory API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _gold(table: str) -> duckdb.DuckDBPyConnection:
    path = GOLD_DIR / f"{table}.parquet"
    if not path.exists():
        raise HTTPException(404, f"gold/{table}.parquet not found — run the pipeline first")
    conn = duckdb.connect()
    conn.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet('{path.as_posix()}')")
    return conn


def _silver() -> duckdb.DuckDBPyConnection:
    if not SILVER_PATH.exists():
        raise HTTPException(404, "silver/jobs.parquet not found — run the pipeline first")
    conn = duckdb.connect()
    conn.execute(f"CREATE VIEW jobs AS SELECT * FROM read_parquet('{SILVER_PATH.as_posix()}')")
    return conn


def _rows(conn: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> list[dict]:
    result = conn.execute(sql, params or [])
    cols = [d[0] for d in result.description]
    return [dict(zip(cols, row)) for row in result.fetchall()]


@app.get("/api/summary")
def summary() -> dict:
    conn = _silver()
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    if total == 0:
        raise HTTPException(404, "no jobs in silver — run the pipeline first")
    sources = conn.execute("SELECT COUNT(DISTINCT source) FROM jobs").fetchone()[0]
    remote_pct = conn.execute(
        "SELECT ROUND(100.0 * SUM(CASE WHEN remote THEN 1 ELSE 0 END) / COUNT(*), 1) FROM jobs"
    ).fetchone()[0]
    top_skill_row = conn.execute("""
        SELECT skill, COUNT(*) AS n FROM jobs, UNNEST(skills) AS t(skill)
        GROUP BY skill ORDER BY n DESC LIMIT 1
    """).fetchone()
    last_ingest = conn.execute("SELECT MAX(ingest_date) FROM jobs").fetchone()[0]
    return {
        "total_jobs": total,
        "sources": sources,
        "remote_pct": remote_pct,
        "top_skill": top_skill_row[0] if top_skill_row else None,
        "last_ingest_date": str(last_ingest) if last_ingest else None,
    }


@app.get("/api/skill-demand")
def skill_demand(limit: int = 20) -> list[dict]:
    conn = _gold("skill_demand")
    return _rows(conn, "SELECT skill, job_count, pct_of_total FROM t ORDER BY job_count DESC LIMIT ?", [limit])


@app.get("/api/remote-split")
def remote_split() -> list[dict]:
    conn = _gold("remote_split")
    return _rows(conn, "SELECT work_type, job_count, pct FROM t ORDER BY job_count DESC")


@app.get("/api/top-categories")
def top_categories(limit: int = 15) -> list[dict]:
    conn = _gold("top_categories")
    return _rows(conn, "SELECT category, job_count FROM t ORDER BY job_count DESC LIMIT ?", [limit])


@app.get("/api/salary-samples")
def salary_samples(limit: int = 50) -> list[dict]:
    conn = _gold("salary_samples")
    return _rows(conn, "SELECT source, salary, count FROM t ORDER BY count DESC LIMIT ?", [limit])


@app.get("/api/daily-volume")
def daily_volume() -> list[dict]:
    conn = _gold("daily_volume")
    return _rows(conn, "SELECT ingest_date, source, job_count FROM t ORDER BY ingest_date, source")


@app.get("/api/skill-cooccurrence")
def skill_cooccurrence(limit: int = 20) -> list[dict]:
    conn = _gold("skill_cooccurrence")
    return _rows(conn, "SELECT skill_a, skill_b, co_occurrences FROM t ORDER BY co_occurrences DESC LIMIT ?", [limit])


@app.get("/api/top-companies")
def top_companies(limit: int = 15) -> list[dict]:
    conn = _silver()
    return _rows(conn, """
        SELECT company, COUNT(*) AS openings
        FROM jobs
        WHERE company IS NOT NULL AND company <> ''
        GROUP BY company
        ORDER BY openings DESC
        LIMIT ?
    """, [limit])


@app.get("/api/source-breakdown")
def source_breakdown() -> list[dict]:
    conn = _silver()
    return _rows(conn, """
        SELECT source, COUNT(*) AS job_count,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM jobs
        GROUP BY source
        ORDER BY job_count DESC
    """)


@app.get("/api/skill-trend")
def skill_trend(skill: str = "python") -> list[dict]:
    conn = _silver()
    return _rows(conn, """
        SELECT DATE_TRUNC('week', posted_date)::DATE AS week_start, COUNT(*) AS job_count
        FROM jobs, UNNEST(skills) AS t(skill)
        WHERE skill = ?
        GROUP BY week_start
        ORDER BY week_start
    """, [skill.lower()])
