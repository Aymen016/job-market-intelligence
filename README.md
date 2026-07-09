# Job Market Observatory

A self-contained daily pipeline that collects tech job postings from three sources, stores every snapshot as Parquet, and lets you run analytical queries — "which skills dominate data-engineering postings this month?" — with plain DuckDB SQL and no cloud account required.

---

## Architecture — the medallion pattern

```
 ┌─────────────────────────────────────────────────────────────────┐
 │                    Prefect daily flow (08:00 UTC)               │
 │                                                                 │
 │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
 │  │   Remotive   │  │  Arbeitnow   │  │  WeWorkRemotely    │    │
 │  │  JSON API    │  │  JSON API    │  │  HTML scrape (BS4) │    │
 │  └──────┬───────┘  └──────┬───────┘  └────────┬───────────┘    │
 │         │                 │                   │                 │
 │         └────────┬────────┘                   │                 │
 │                  ▼                             │                 │
 │         ┌────────────────────────────────────────────────────┐  │
 │         │  BRONZE  (raw Parquet, partitioned by source+date) │  │
 │         │  data/bronze/source=*/ingest_date=*/data.parquet   │  │
 │         └───────────────────────┬────────────────────────────┘  │
 │                                 │                               │
 │                                 ▼                               │
 │         ┌────────────────────────────────────────────────────┐  │
 │         │  SILVER  (unified, deduplicated, skills tagged)    │  │
 │         │  data/silver/jobs.parquet                          │  │
 │         └───────────────────────┬────────────────────────────┘  │
 │                                 │                               │
 │                                 ▼                               │
 │         ┌────────────────────────────────────────────────────┐  │
 │         │  GOLD    (analytical mart tables)                  │  │
 │         │  data/gold/{skill_demand, remote_split, …}.parquet │  │
 │         └────────────────────────────────────────────────────┘  │
 └─────────────────────────────────────────────────────────────────┘
```

### Bronze — raw truth, never modified
Every run writes whatever each source returned, untouched, into a date-partitioned directory tree.  If you later find a bug in the cleaning logic you can reprocess history instead of having lost the originals.

### Silver — one clean table
DuckDB reads all bronze Parquet files directly, maps each source's field names to a common schema (`title, company, location, remote, tags, salary, url, posted_date, source, description`), strips HTML from descriptions, deduplicates by URL, and tags each posting with every matching skill keyword from a curated list.

### Gold — the answers
A second DuckDB pass aggregates silver into small mart tables built to answer specific questions: skill demand rankings, remote/onsite split, salary samples, daily volume, skill co-occurrence pairs.

---

## Project layout

```
job-market-observatory/
├── pipeline/
│   ├── config.py              ← paths, URLs, skills keyword list
│   ├── bronze.py              ← write raw data to Parquet
│   ├── silver.py              ← normalize, deduplicate, extract skills
│   ├── gold.py                ← aggregate mart tables
│   └── extractors/
│       ├── remotive.py        ← Remotive JSON API
│       ├── arbeitnow.py       ← Arbeitnow JSON API (paginated)
│       └── weworkremotely.py  ← WeWorkRemotely HTML scraper
├── flows/
│   └── daily_flow.py          ← Prefect flow + tasks + schedule
├── analysis/
│   └── queries.py             ← ad-hoc DuckDB query functions
├── data/                      ← auto-created; not committed to git
│   ├── bronze/
│   ├── silver/
│   └── gold/
└── requirements.txt
```

---

## Setup

**Python 3.11+ recommended.**

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Running the pipeline

### One-shot run (no Prefect server needed)

```bash
python flows/daily_flow.py
```

Prefect logs each task's start, completion, and record counts to stdout.
The full extract → bronze → silver → gold cycle completes in roughly 30–60 seconds depending on network speed.

### Self-scheduling (daily at 08:00 UTC)

```bash
python flows/daily_flow.py --serve
```

This keeps the process alive and re-runs the flow every day.  Stop it with `Ctrl+C`.

---

## Querying the data

### Pre-built queries

```bash
python analysis/queries.py
```

Prints: top-20 skills, top skills in data-engineer roles, remote split, top companies, weekly trend for Python and dbt, skill co-occurrence pairs, source breakdown.

### Ad-hoc DuckDB in a REPL or notebook

```python
import duckdb

conn = duckdb.connect()
conn.execute("CREATE VIEW jobs AS SELECT * FROM read_parquet('data/silver/jobs.parquet')")

# Which skills appear most in data-engineering postings?
conn.execute("""
    SELECT skill, COUNT(*) AS jobs
    FROM jobs, UNNEST(skills) AS t(skill)
    WHERE lower(title) LIKE '%data engineer%'
    GROUP BY skill
    ORDER BY jobs DESC
    LIMIT 15
""").show()

# How has Python demand changed week-over-week?
conn.execute("""
    SELECT
        DATE_TRUNC('week', posted_date)::DATE AS week,
        COUNT(*) AS python_jobs
    FROM jobs, UNNEST(skills) AS t(skill)
    WHERE skill = 'python'
    GROUP BY week
    ORDER BY week
""").show()
```

### Reading gold mart tables directly

```python
import duckdb
duckdb.execute("SELECT * FROM read_parquet('data/gold/skill_demand.parquet')").show()
duckdb.execute("SELECT * FROM read_parquet('data/gold/skill_cooccurrence.parquet')").show()
```

---

## Data sources

| Source | Method | Notes |
|---|---|---|
| [Remotive](https://remotive.com/api/remote-jobs) | JSON API | No auth required; up to ~300 jobs/call |
| [Arbeitnow](https://www.arbeitnow.com/api/job-board-api) | JSON API (paginated) | No auth required; up to 5 pages × ~100 jobs |
| [We Work Remotely](https://weworkremotely.com/) | HTML scrape (BeautifulSoup) | No API; scrapes listing page |

---

## Skills tracked

The keyword list in `pipeline/config.py` covers:

- **Languages**: Python, SQL, Scala, Java, Go, Rust, TypeScript, Bash …
- **Orchestration**: Airflow, Prefect, Dagster, dbt, Kafka, Spark, Flink …
- **Databases / stores**: PostgreSQL, MongoDB, Redis, BigQuery, Snowflake, Iceberg …
- **Cloud / infra**: AWS, GCP, Azure, Docker, Kubernetes, Terraform …
- **BI / observability**: Looker, Tableau, Power BI, Grafana …

Add or remove keywords in `SKILLS` and re-run silver to reprocess history instantly — all bronze files are preserved.

---

## .gitignore suggestion

```
.venv/
data/
__pycache__/
*.pyc
.prefect/
```
