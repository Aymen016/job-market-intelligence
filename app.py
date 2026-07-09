"""
Job Market Intelligence — Dashboard (serving layer)
===================================================
A thin presentation layer over the DuckDB / Parquet job-market lake.

It reads straight from your lake and auto-detects columns, so it runs on your
real data without you renaming anything. Edit the CONFIG block below to point it
at your source, then:

    pip install -r requirements.txt
    streamlit run app.py

Deploy free at https://share.streamlit.io (Streamlit Community Cloud) to get a
live demo link for your portfolio.
"""

from __future__ import annotations

import re
import duckdb
import pandas as pd
import altair as alt
import streamlit as st

# ----------------------------------------------------------------------------
# CONFIG — point this at your lake. Only one of the two paths needs to be valid.
# ----------------------------------------------------------------------------
# Option A: a DuckDB database file. Leave TABLE_NAME as None to auto-pick the
#           first table, or set it explicitly (e.g. "jobs").
DUCKDB_PATH = "job_market.duckdb"
TABLE_NAME = None

# Option B: Parquet file(s). Used only if the DuckDB file above isn't found.
#           A glob is fine, e.g. "data/*.parquet" or "data/**/*.parquet".
PARQUET_GLOB = "data/silver/*.parquet"

# ----------------------------------------------------------------------------
# Column detection — candidate names per semantic role (case-insensitive).
# Add your own column names here if detection misses something.
# ----------------------------------------------------------------------------
CANDIDATES = {
    "title": ["title", "job_title", "role", "position", "job_role", "job_name"],
    "company": ["company", "company_name", "employer", "organization", "org"],
    "location": ["location", "job_location", "city", "place", "region", "country"],
    "salary": [
        "salary", "avg_salary", "salary_avg", "salary_usd", "annual_salary",
        "median_salary", "compensation", "pay", "salary_max", "salary_min",
    ],
    "date": [
        "posted_date", "date_posted", "posted_at", "date", "created_at",
        "publish_date", "listing_date", "scraped_at", "ingested_at",
    ],
    "skills": [
        "skills", "skill", "tech_stack", "technologies", "tags",
        "required_skills", "keywords",
    ],
    "source": ["source", "site", "platform", "job_source", "board"],
    "seniority": ["seniority", "level", "experience_level", "job_level"],
    "emp_type": ["employment_type", "job_type", "type", "contract_type"],
}

SKILL_SPLIT = re.compile(r"[;,|/]| and ", flags=re.IGNORECASE)

st.set_page_config(
    page_title="Job Market Intelligence",
    page_icon="📊",
    layout="wide",
)


# ----------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading the lake…")
def load_data() -> tuple[pd.DataFrame, str]:
    """Load the dataset from DuckDB (preferred) or Parquet. Returns (df, source_desc)."""
    import os

    con = duckdb.connect()

    if DUCKDB_PATH and os.path.exists(DUCKDB_PATH):
        con.execute(f"ATTACH '{DUCKDB_PATH}' AS lake (READ_ONLY)")
        tables = con.execute("SHOW ALL TABLES").df()
        lake_tables = tables[tables["database"] == "lake"]["name"].tolist()
        if not lake_tables:
            raise RuntimeError(f"No tables found inside {DUCKDB_PATH}")
        table = TABLE_NAME or lake_tables[0]
        df = con.execute(f'SELECT * FROM lake."{table}"').df()
        return df, f"DuckDB · {DUCKDB_PATH} · table `{table}`"

    # Fall back to Parquet
    df = con.execute(
        f"SELECT * FROM read_parquet('{PARQUET_GLOB}', union_by_name=true)"
    ).df()
    return df, f"Parquet · {PARQUET_GLOB}"


def detect_columns(df: pd.DataFrame) -> dict[str, str | None]:
    """Map each semantic role to a real column name (or None)."""
    lower = {c.lower(): c for c in df.columns}
    found: dict[str, str | None] = {}
    for role, names in CANDIDATES.items():
        found[role] = next((lower[n] for n in names if n in lower), None)
    return found


def to_numeric_salary(series: pd.Series) -> pd.Series:
    """Best-effort coercion of a salary column to numbers (handles $, commas, k)."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    def parse(v):
        if pd.isna(v):
            return None
        s = str(v).lower().replace(",", "").replace("$", "").strip()
        mult = 1000 if s.endswith("k") else 1
        s = s.rstrip("k")
        m = re.search(r"\d+(\.\d+)?", s)
        return float(m.group()) * mult if m else None

    return series.map(parse)


def explode_skills(series: pd.Series) -> pd.Series:
    """Flatten a skills column (list-typed or delimited string) into individual skills."""
    out: list[str] = []
    for v in series.dropna():
        if isinstance(v, (list, tuple)):
            parts = v
        else:
            parts = SKILL_SPLIT.split(str(v))
        for p in parts:
            p = str(p).strip()
            if p and len(p) < 40:
                out.append(p)
    return pd.Series(out, dtype="object")


def top_n_chart(counts: pd.Series, label: str, n: int = 12):
    """Horizontal bar chart of the top-N categories."""
    data = counts.head(n).rename_axis(label).reset_index(name="Postings")
    return (
        alt.Chart(data)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X("Postings:Q", title="Postings"),
            y=alt.Y(f"{label}:N", sort="-x", title=None),
            tooltip=[label, "Postings"],
        )
        .properties(height=min(30 * len(data) + 20, 420))
    )


# ----------------------------------------------------------------------------
# App
# ----------------------------------------------------------------------------
st.title("📊 Job Market Intelligence")
st.caption("Serving layer over the DuckDB / Parquet lake — Prefect ingest → Parquet → DuckDB → here.")

try:
    df, source_desc = load_data()
except Exception as exc:  # noqa: BLE001
    st.error(
        "Couldn't load the data. Check the CONFIG paths at the top of `app.py`.\n\n"
        f"**Details:** {exc}"
    )
    st.stop()

cols = detect_columns(df)

# --- Sidebar filters --------------------------------------------------------
st.sidebar.header("Filters")
st.sidebar.caption(source_desc)

filtered = df.copy()

# Date filter
if cols["date"]:
    filtered[cols["date"]] = pd.to_datetime(filtered[cols["date"]], errors="coerce")
    valid_dates = filtered[cols["date"]].dropna()
    if not valid_dates.empty:
        dmin, dmax = valid_dates.min().date(), valid_dates.max().date()
        if dmin < dmax:
            start, end = st.sidebar.slider(
                "Posted between", min_value=dmin, max_value=dmax, value=(dmin, dmax)
            )
            mask = filtered[cols["date"]].dt.date.between(start, end)
            filtered = filtered[mask | filtered[cols["date"]].isna()]

# Categorical filters (multiselect for anything with a manageable set of values)
for role in ["source", "location", "seniority", "emp_type"]:
    col = cols[role]
    if col and 1 < filtered[col].nunique() <= 60:
        options = sorted(filtered[col].dropna().astype(str).unique())
        chosen = st.sidebar.multiselect(col.replace("_", " ").title(), options)
        if chosen:
            filtered = filtered[filtered[col].astype(str).isin(chosen)]

# Free-text search on title
if cols["title"]:
    q = st.sidebar.text_input("Search role / title")
    if q:
        filtered = filtered[
            filtered[cols["title"]].astype(str).str.contains(q, case=False, na=False)
        ]

# --- KPIs -------------------------------------------------------------------
k = st.columns(4)
k[0].metric("Postings", f"{len(filtered):,}")
if cols["company"]:
    k[1].metric("Companies", f"{filtered[cols['company']].nunique():,}")
if cols["location"]:
    k[2].metric("Locations", f"{filtered[cols['location']].nunique():,}")
if cols["salary"]:
    sal = to_numeric_salary(filtered[cols["salary"]]).dropna()
    if not sal.empty:
        k[3].metric("Median salary", f"{sal.median():,.0f}")
elif cols["date"] and filtered[cols["date"]].notna().any():
    span = filtered[cols["date"]].dropna()
    k[3].metric("Date range (days)", f"{(span.max() - span.min()).days:,}")

st.divider()

# --- Charts -----------------------------------------------------------------
row1 = st.columns(2)

with row1[0]:
    if cols["title"]:
        st.subheader("Top roles")
        st.altair_chart(
            top_n_chart(filtered[cols["title"]].astype(str).value_counts(), "Role"),
            use_container_width=True,
        )
    else:
        st.info("No role/title column detected.")

with row1[1]:
    if cols["skills"]:
        st.subheader("Most-demanded skills")
        skills = explode_skills(filtered[cols["skills"]])
        if not skills.empty:
            st.altair_chart(
                top_n_chart(skills.value_counts(), "Skill"),
                use_container_width=True,
            )
        else:
            st.info("Skills column found but no values to show.")
    elif cols["location"]:
        st.subheader("Top locations")
        st.altair_chart(
            top_n_chart(filtered[cols["location"]].astype(str).value_counts(), "Location"),
            use_container_width=True,
        )

row2 = st.columns(2)

with row2[0]:
    if cols["date"] and filtered[cols["date"]].notna().any():
        st.subheader("Postings over time")
        ts = (
            filtered.dropna(subset=[cols["date"]])
            .set_index(cols["date"])
            .assign(_n=1)["_n"]
            .resample("W")
            .sum()
            .rename_axis("Week")
            .reset_index(name="Postings")
        )
        line = (
            alt.Chart(ts)
            .mark_line(point=True)
            .encode(
                x=alt.X("Week:T", title=None),
                y=alt.Y("Postings:Q"),
                tooltip=["Week", "Postings"],
            )
            .properties(height=320)
        )
        st.altair_chart(line, use_container_width=True)

with row2[1]:
    if cols["salary"]:
        sal = to_numeric_salary(filtered[cols["salary"]]).dropna()
        if not sal.empty:
            st.subheader("Salary distribution")
            hist = (
                alt.Chart(pd.DataFrame({"Salary": sal}))
                .mark_bar()
                .encode(
                    x=alt.X("Salary:Q", bin=alt.Bin(maxbins=30)),
                    y=alt.Y("count()", title="Postings"),
                    tooltip=[alt.Tooltip("count()", title="Postings")],
                )
                .properties(height=320)
            )
            st.altair_chart(hist, use_container_width=True)
    elif cols["company"]:
        st.subheader("Top companies hiring")
        st.altair_chart(
            top_n_chart(filtered[cols["company"]].astype(str).value_counts(), "Company"),
            use_container_width=True,
        )

# --- Raw data + export ------------------------------------------------------
st.divider()
with st.expander(f"Browse data ({len(filtered):,} rows)"):
    st.dataframe(filtered, use_container_width=True, height=380)
    st.download_button(
        "Download filtered CSV",
        filtered.to_csv(index=False).encode("utf-8"),
        file_name="job_market_filtered.csv",
        mime="text/csv",
    )

# --- Footer / detected schema (handy while wiring up) -----------------------
with st.sidebar.expander("Detected columns"):
    st.json({role: col for role, col in cols.items() if col})
