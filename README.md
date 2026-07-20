# Job Market Observatory

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Prefect](https://img.shields.io/badge/orchestration-Prefect-1857e0)
![DuckDB](https://img.shields.io/badge/query%20engine-DuckDB-FFC44C)
![React](https://img.shields.io/badge/dashboard-React%20%2B%20Vite-61DAFB)

A self-contained daily pipeline that collects tech job postings from three sources,
stores every snapshot as Parquet, and answers questions like *"which skills dominate
data-engineering postings this month?"* — with plain DuckDB SQL, a browsable
dashboard, and no cloud account required.

---

## Demo

<!--
  Add your recording here once it's ready, for example:
  ![Dashboard demo](docs/demo.gif)

  Or, if you upload the video through a GitHub PR/issue comment, GitHub gives you
  a hosted https://github.com/<user>/<repo>/assets/... URL — paste that directly
  as a markdown image/link and GitHub renders it as an inline video player.
-->





https://github.com/user-attachments/assets/caa8d9f1-1f96-40de-9eb2-2955b3e9df80




---

## Features

- **Three ingestion sources** — Remotive and Arbeitnow JSON APIs, plus a
  WeWorkRemotely HTML scraper — running in parallel with automatic retries.
- **Medallion architecture** (bronze → silver → gold) so raw data is never lost
  and the whole history can be reprocessed if the cleaning logic changes.
- **~90 skill keywords** auto-tagged on every posting, with demand rankings and
  co-occurrence pairs computed for free.
- **Prefect orchestration** — run once, or `--serve` for a self-scheduling daily job.
- **A web dashboard** (FastAPI + React) that visualizes the gold tables live.
- Zero infrastructure: everything is local Parquet files queried directly by DuckDB.

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

**Bronze — raw truth, never modified.** Every run writes whatever each source
returned, untouched, into a date-partitioned directory tree. If a bug is later
found in the cleaning logic, history can be reprocessed instead of lost.

**Silver — one clean table.** DuckDB reads all bronze Parquet files directly,
maps each source's field names to a common schema (`title, company, location,
remote, tags, salary, url, posted_date, source, description`), strips HTML from
descriptions, deduplicates by URL, and tags each posting with every matching
skill keyword from a curated list.

**Gold — the answers.** A second DuckDB pass aggregates silver into small mart
tables built to answer specific questions: skill demand rankings, remote/on-site
split, salary samples, daily volume, skill co-occurrence pairs.

---

## Quick start

**Requires Python 3.11+ and Node.js 18+.**

```bash
# 1. Clone and enter the project
git clone https://github.com/Aymen016/job-market-intelligence.git
cd job-market-intelligence

# 2. Create a virtual environment and install Python dependencies
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

# 3. Run the pipeline once — extracts, cleans, and aggregates into data/
python -m flows.daily_flow

# 4. Start the API (in one terminal)
python -m uvicorn backend.main:app --port 8000

# 5. Start the dashboard (in a second terminal)
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173** — the dashboard shows top skills, remote/on-site
split, top categories and companies, skill co-occurrence pairs, daily posting
volume, and disclosed salaries, all read live from whatever the pipeline last
produced.

### Keep it running automatically

```bash
python -m flows.daily_flow --serve
```

Keeps the process alive and re-runs the flow every day at 08:00 UTC. Stop it with `Ctrl+C`.

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
├── backend/
│   └── main.py                ← FastAPI — serves gold/silver as JSON
├── frontend/                  ← Vite + React dashboard
├── data/                      ← auto-created; not committed to git
│   ├── bronze/
│   ├── silver/
│   └── gold/
└── requirements.txt
```

---

## Querying the data

### Pre-built queries

```bash
python -m analysis.queries
```

Prints: top-20 skills, top skills in data-engineer roles, remote split, top
companies, weekly trend for Python and dbt, skill co-occurrence pairs, source
breakdown.

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

Add or remove keywords in `SKILLS` and re-run silver to reprocess history
instantly — all bronze files are preserved.

---

## Known limitations

- The WeWorkRemotely scraper currently returns 0 records on most runs — its
  target markup has likely drifted from what `pipeline/extractors/weworkremotely.py`
  expects. Remotive and Arbeitnow still cover the pipeline.
- Only Remotive discloses salary; Arbeitnow's `salary_samples` rows come back empty.
- Trend charts (daily volume, weekly skill trend) are only as deep as your
  collected history — they fill in as the pipeline runs on more days.

---

## License

[MIT](LICENSE) © Aymen Baig
