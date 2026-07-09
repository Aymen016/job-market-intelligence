"""Shared configuration: paths, URLs, HTTP settings, skills keyword list."""
from __future__ import annotations

from pathlib import Path

# ── Directory layout ──────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
DATA_DIR   = BASE_DIR / "data"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR   = DATA_DIR / "gold"

for _d in (BRONZE_DIR, SILVER_DIR, GOLD_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Source endpoints ──────────────────────────────────────────────────────────
REMOTIVE_URL  = "https://remotive.com/api/remote-jobs"
ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"
WWR_URL       = "https://weworkremotely.com/"
WWR_BASE_URL  = "https://weworkremotely.com"

# ── HTTP ──────────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 30  # seconds

HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Skills keyword list (lower-case) ─────────────────────────────────────────
# Used in the silver layer to tag each posting with the skills it mentions.
SKILLS: list[str] = [
    # Languages
    "python", "sql", "scala", "java", "golang", "rust", "r",
    "typescript", "javascript", "bash",
    # Orchestration / pipeline
    "spark", "pyspark", "flink", "beam", "kafka", "airflow",
    "dbt", "dagster", "luigi", "prefect", "celery",
    # Data-science libraries
    "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch",
    "xgboost", "lightgbm",
    # Databases & data stores
    "postgresql", "mysql", "sqlite", "mongodb", "cassandra",
    "redis", "elasticsearch", "opensearch", "neo4j",
    "bigquery", "snowflake", "redshift", "databricks",
    "hive", "hadoop",
    # Table formats
    "iceberg", "delta lake", "hudi",
    # Cloud & infra
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
    "helm", "ansible", "jenkins", "github actions",
    # BI & observability
    "looker", "tableau", "power bi", "metabase", "grafana",
    "superset", "prometheus",
    # Practices / domains
    "etl", "elt", "mlops", "devops", "ci/cd",
    "data engineering", "data science",
    "machine learning", "deep learning", "nlp",
    "llm", "rag",
    # File formats / protocols
    "parquet", "avro", "protobuf", "grpc", "rest", "graphql",
    # Tools
    "git", "linux",
]
