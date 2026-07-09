"""Bronze layer — land raw data as Parquet, partitioned by source and date.

Layout on disk::

    data/bronze/
    └── source=remotive/
        └── ingest_date=2026-07-09/
            └── data.parquet
    └── source=arbeitnow/
        └── ingest_date=2026-07-09/
            └── data.parquet
    └── source=weworkremotely/
        └── ingest_date=2026-07-09/
            └── data.parquet

The rule at this layer: **write records exactly as received — no cleaning**.
If the cleaning logic is later found to be wrong, the raw truth is preserved
and history can be reprocessed.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd

from pipeline.config import BRONZE_DIR

logger = logging.getLogger(__name__)


def write(
    source: str,
    records: list[dict[str, Any]],
    ingest_date: date | None = None,
) -> str:
    """
    Persist *records* for *source* to the bronze partition for *ingest_date*.

    Parameters
    ----------
    source:
        Short source identifier, e.g. ``"remotive"``.
    records:
        Raw records exactly as returned by the extractor.
    ingest_date:
        Partition date; defaults to today.

    Returns
    -------
    str
        Absolute path of the written Parquet file.
    """
    if ingest_date is None:
        ingest_date = date.today()

    partition_dir = BRONZE_DIR / f"source={source}" / f"ingest_date={ingest_date}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    out_path = partition_dir / "data.parquet"

    df = pd.DataFrame(records)

    # Ensure Python list columns survive the round-trip to Parquet correctly:
    # a column whose first non-null entry is a list must not contain scalars.
    for col in df.columns:
        first_valid = df[col].dropna()
        if not first_valid.empty and isinstance(first_valid.iloc[0], list):
            df[col] = df[col].apply(lambda v: v if isinstance(v, list) else [])

    df.to_parquet(out_path, index=False, engine="pyarrow")
    logger.info("Bronze: %s → %d records → %s", source, len(df), out_path)
    return str(out_path)
