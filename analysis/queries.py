"""Interactive analytical queries against the job-market observatory.

Run all built-in queries::

    python analysis/queries.py

Or import the functions in a notebook / REPL for ad-hoc exploration::

    from analysis.queries import top_skills, skills_in_category
    top_skills(30)
    skills_in_category("data engineer")
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

DATA_DIR    = Path(__file__).parent.parent / "data"
SILVER_PATH = str(DATA_DIR / "silver" / "jobs.parquet")
GOLD_DIR    = DATA_DIR / "gold"


def _conn() -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection with the silver table registered as a view."""
    if not Path(SILVER_PATH).exists():
        print(
            "No silver data found. Run the pipeline first:\n"
            "    python flows/daily_flow.py",
            file=sys.stderr,
        )
        sys.exit(1)
    conn = duckdb.connect()
    conn.execute(f"CREATE OR REPLACE VIEW jobs AS SELECT * FROM read_parquet('{SILVER_PATH}')")
    return conn


# ── Query functions ───────────────────────────────────────────────────────────

def top_skills(n: int = 20) -> None:
    """Print the *n* most-demanded skills across all postings."""
    print(f"\n{'─'*50}")
    print(f"  Top {n} most-demanded skills (all sources)")
    print(f"{'─'*50}")
    _conn().execute(f"""
        SELECT
            skill,
            COUNT(*)                                               AS jobs,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2)    AS pct
        FROM jobs, UNNEST(skills) AS t(skill)
        GROUP BY skill
        ORDER BY jobs DESC
        LIMIT {n}
    """).show()


def skills_in_category(category: str = "data engineer", n: int = 15) -> None:
    """Print the top skills in postings whose title or category matches *category*."""
    print(f"\n{'─'*50}")
    print(f"  Top skills in '{category}' postings (top {n})")
    print(f"{'─'*50}")
    pattern = f"%{category.lower()}%"
    _conn().execute(f"""
        SELECT
            skill,
            COUNT(*) AS jobs
        FROM jobs, UNNEST(skills) AS t(skill)
        WHERE lower(category) LIKE ? OR lower(title) LIKE ?
        GROUP BY skill
        ORDER BY jobs DESC
        LIMIT {n}
    """, [pattern, pattern]).show()


def remote_split() -> None:
    """Print remote vs on-site breakdown."""
    print(f"\n{'─'*50}")
    print("  Remote vs On-site split")
    print(f"{'─'*50}")
    _conn().execute("""
        SELECT
            CASE WHEN remote THEN 'Remote' ELSE 'On-site' END   AS work_type,
            COUNT(*)                                             AS jobs,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1)  AS pct
        FROM jobs
        GROUP BY remote
        ORDER BY jobs DESC
    """).show()


def top_companies(n: int = 15) -> None:
    """Print the companies with the most open roles."""
    print(f"\n{'─'*50}")
    print(f"  Top {n} hiring companies")
    print(f"{'─'*50}")
    _conn().execute(f"""
        SELECT
            company,
            COUNT(*) AS openings
        FROM jobs
        WHERE company IS NOT NULL AND company <> ''
        GROUP BY company
        ORDER BY openings DESC
        LIMIT {n}
    """).show()


def weekly_skill_trend(skill: str = "python") -> None:
    """Print weekly posting counts for a specific *skill*."""
    print(f"\n{'─'*50}")
    print(f"  Weekly trend for skill: '{skill}'")
    print(f"{'─'*50}")
    _conn().execute("""
        SELECT
            DATE_TRUNC('week', posted_date)::DATE  AS week_start,
            COUNT(*)                               AS job_count
        FROM jobs, UNNEST(skills) AS t(skill)
        WHERE skill = ?
        GROUP BY week_start
        ORDER BY week_start
    """, [skill.lower()]).show()


def skill_cooccurrence(n: int = 20) -> None:
    """Print the most common skill pairs that appear together in postings."""
    print(f"\n{'─'*50}")
    print(f"  Top {n} skill co-occurrence pairs")
    print(f"{'─'*50}")
    _conn().execute(f"""
        SELECT
            a.skill  AS skill_a,
            b.skill  AS skill_b,
            COUNT(*) AS jobs
        FROM jobs,
             UNNEST(skills) AS a(skill),
             UNNEST(skills) AS b(skill)
        WHERE a.skill < b.skill
        GROUP BY skill_a, skill_b
        ORDER BY jobs DESC
        LIMIT {n}
    """).show()


def source_breakdown() -> None:
    """Print how many postings came from each source."""
    print(f"\n{'─'*50}")
    print("  Postings per source")
    print(f"{'─'*50}")
    _conn().execute("""
        SELECT
            source,
            COUNT(*)                                              AS jobs,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1)   AS pct
        FROM jobs
        GROUP BY source
        ORDER BY jobs DESC
    """).show()


def salary_overview() -> None:
    """Print a sample of disclosed salary strings."""
    print(f"\n{'─'*50}")
    print("  Salary samples (where disclosed)")
    print(f"{'─'*50}")
    gold_path = str(GOLD_DIR / "salary_samples.parquet")
    if not Path(gold_path).exists():
        print("  Run the pipeline to generate gold/salary_samples.parquet")
        return
    duckdb.execute(f"SELECT * FROM read_parquet('{gold_path}') LIMIT 30").show()


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    top_skills()
    skills_in_category("data engineer")
    skills_in_category("machine learning")
    remote_split()
    top_companies()
    weekly_skill_trend("python")
    weekly_skill_trend("dbt")
    skill_cooccurrence()
    source_breakdown()
    salary_overview()
