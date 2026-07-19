"""
Job Market Intelligence — Dashboard (serving layer)
===================================================
Presentation layer over the DuckDB / Parquet job-market lake produced by the
bronze -> silver -> gold pipeline (see flows/daily_flow.py).

    pip install -r requirements.txt
    streamlit run app.py

Deploy free at https://share.streamlit.io (Streamlit Community Cloud) to get a
live demo link for your portfolio.
"""

from __future__ import annotations

import itertools
from collections import Counter

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
SILVER_PATH = "data/silver/jobs.parquet"
REPO_URL = "https://github.com/Aymen016/job-market-intelligence"

# Validated categorical palette (dataviz skill reference palette, light mode)
BLUE = "#2a78d6"
AQUA = "#1baf7a"
VIOLET = "#4a3aa7"
ORANGE = "#eb6834"
INK_SECONDARY = "#52514e"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

st.set_page_config(
    page_title="Job Market Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1200px; }

      .hero {
        background: linear-gradient(135deg, #0d1b2a 0%, #16324f 55%, #1c5cab 100%);
        color: #fff;
        padding: 2.1rem 2.4rem;
        border-radius: 16px;
        margin-bottom: 1.6rem;
      }
      .hero h1 { margin: 0 0 .4rem 0; font-size: 1.9rem; font-weight: 700; letter-spacing: -.02em; }
      .hero p { margin: 0; color: rgba(255,255,255,.78); font-size: .98rem; max-width: 680px; }
      .hero .badges { margin-top: 1rem; display: flex; gap: .5rem; flex-wrap: wrap; }
      .hero .badge {
        display: inline-flex; align-items: center; gap: .35rem;
        background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.18);
        padding: .32rem .75rem; border-radius: 999px; font-size: .78rem; color: #fff;
      }

      .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: .9rem; margin-bottom: 1.6rem; }
      .stat-tile { background: #fff; border: 1px solid rgba(11,11,11,.10); border-radius: 12px; padding: 1.05rem 1.2rem; }
      .stat-tile .label { font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: #898781; font-weight: 600; }
      .stat-tile .value { font-size: 1.65rem; font-weight: 700; color: #0b0b0b; margin-top: .2rem; line-height: 1.15; }
      .stat-tile .sub { font-size: .78rem; color: #52514e; margin-top: .15rem; }
      @media (max-width: 900px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } }

      .section-title { display: flex; align-items: flex-start; gap: .55rem; margin: .1rem 0 .8rem 0; }
      .section-title .bar { width: 4px; height: 1.15rem; border-radius: 2px; background: #2a78d6; margin-top: .18rem; flex-shrink: 0; }
      .section-title h3 { margin: 0; font-size: 1.05rem; font-weight: 700; color: #0b0b0b; }
      .section-title p { margin: .1rem 0 0 0; color: #898781; font-size: .82rem; }

      .prop-bar { display: flex; height: 34px; border-radius: 8px; overflow: hidden; border: 1px solid rgba(11,11,11,.08); }
      .prop-seg { display: flex; align-items: center; justify-content: center; color: #fff; font-size: .8rem; font-weight: 600; }
      .prop-legend { display: flex; gap: 1.2rem; margin-top: .6rem; font-size: .82rem; color: #52514e; }
      .prop-legend .dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: .4rem; }

      .footer-note { margin-top: 1.5rem; padding-top: 1.1rem; border-top: 1px solid rgba(11,11,11,.08); color: #898781; font-size: .8rem; }
      #MainMenu { visibility: visible; }
      footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

alt.theme.enable("none")


def styled(chart: alt.Chart, height: int) -> alt.Chart:
    return (
        chart.properties(height=height, background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(
            grid=True,
            gridColor=GRID,
            gridDash=[2, 3],
            domainColor=AXIS,
            tickColor=AXIS,
            labelColor=INK_SECONDARY,
            titleColor=INK_SECONDARY,
            labelFontSize=11,
            titleFontSize=11,
        )
        .configure_legend(labelColor=INK_SECONDARY, titleColor=INK_SECONDARY, orient="top", direction="horizontal")
    )


def ranked_bar(df: pd.DataFrame, cat: str, val: str, color: str, n: int = 12, val_title: str = "Postings") -> alt.Chart:
    data = df.head(n)
    row_h = 28
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusEnd=4, size=16, color=color)
        .encode(
            x=alt.X(f"{val}:Q", title=val_title),
            y=alt.Y(f"{cat}:N", sort="-x", title=None, axis=alt.Axis(grid=False)),
            tooltip=[alt.Tooltip(f"{cat}:N", title="Value"), alt.Tooltip(f"{val}:Q", title=val_title)],
        )
    )
    return styled(chart, height=min(row_h * len(data) + 30, 420))


def stat_tile(label: str, value: str, sub: str = "") -> str:
    sub_html = f"<div class='sub'>{sub}</div>" if sub else ""
    return f"<div class='stat-tile'><div class='label'>{label}</div><div class='value'>{value}</div>{sub_html}</div>"


def section_header(title: str, subtitle: str = "") -> None:
    sub_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f"<div class='section-title'><div class='bar'></div><div><h3>{title}</h3>{sub_html}</div></div>",
        unsafe_allow_html=True,
    )


def proportion_bar(segments: list[tuple[str, float, str]]) -> str:
    """segments: list of (label, pct, color)."""
    seg_html = "".join(
        f"<div class='prop-seg' style='width:{pct}%; background:{color};'>{pct:.0f}%</div>"
        for _, pct, color in segments
        if pct > 0
    )
    legend_html = "".join(
        f"<span><span class='dot' style='background:{color};'></span>{label} — {pct:.1f}%</span>"
        for label, pct, color in segments
    )
    return f"<div class='prop-bar'>{seg_html}</div><div class='prop-legend'>{legend_html}</div>"


# ----------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading the lake…")
def load_jobs() -> pd.DataFrame:
    con = duckdb.connect()
    df = con.execute(f"SELECT * FROM read_parquet('{SILVER_PATH}')").df()
    df["posted_date"] = pd.to_datetime(df["posted_date"], errors="coerce")
    return df


def explode_list_col(series: pd.Series) -> pd.Series:
    out: list[str] = []
    for v in series.dropna():
        items = v if isinstance(v, (list, tuple)) or hasattr(v, "tolist") else [v]
        for item in items:
            s = str(item).strip()
            if s:
                out.append(s)
    return pd.Series(out, dtype="object")


try:
    jobs = load_jobs()
except Exception as exc:  # noqa: BLE001
    st.error(
        "Couldn't load `data/silver/jobs.parquet`. Run the pipeline first:\n\n"
        "```bash\npython flows/daily_flow.py\n```\n\n"
        f"**Details:** {exc}"
    )
    st.stop()

if jobs.empty:
    st.warning("The silver table is empty — run `python flows/daily_flow.py` to collect postings.")
    st.stop()

# ----------------------------------------------------------------------------
# Sidebar filters
# ----------------------------------------------------------------------------
st.sidebar.markdown("### 📊 Job Market Intelligence")
st.sidebar.caption("Filters apply live across every tab.")
st.sidebar.divider()

sources = st.sidebar.multiselect("Source", sorted(jobs["source"].dropna().unique()))
work_type = st.sidebar.radio("Work type", ["All", "Remote", "On-site"], horizontal=True)
categories = st.sidebar.multiselect("Category", sorted(jobs["category"].dropna().unique()))
search = st.sidebar.text_input("Search title")

filtered = jobs.copy()
if sources:
    filtered = filtered[filtered["source"].isin(sources)]
if work_type == "Remote":
    filtered = filtered[filtered["remote"]]
elif work_type == "On-site":
    filtered = filtered[~filtered["remote"]]
if categories:
    filtered = filtered[filtered["category"].isin(categories)]
if search:
    filtered = filtered[filtered["title"].str.contains(search, case=False, na=False)]

st.sidebar.divider()
st.sidebar.caption(f"{len(filtered):,} of {len(jobs):,} postings match your filters.")

# ----------------------------------------------------------------------------
# Hero
# ----------------------------------------------------------------------------
span_start = jobs["posted_date"].min()
span_end = jobs["posted_date"].max()
span_txt = f"{span_start:%b %d} – {span_end:%b %d, %Y}" if pd.notna(span_start) else "—"

st.markdown(
    f"""
    <div class="hero">
      <h1>📊 Job Market Intelligence</h1>
      <p>A daily-refreshed view of tech job postings, aggregated from a bronze → silver → gold
      DuckDB / Parquet lake — tracking roles, skills, remote share, and pay across sources.</p>
      <div class="badges">
        <span class="badge">🗓️ {span_txt}</span>
        <span class="badge">🔗 {jobs['source'].nunique()} sources</span>
        <span class="badge">🧩 {len(jobs):,} postings tracked</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if filtered.empty:
    st.info("No postings match the current filters — try widening them in the sidebar.")
    st.stop()

# ----------------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------------
tab_overview, tab_trends, tab_skills, tab_pay, tab_explore = st.tabs(
    ["Overview", "Trends", "Skills", "Location & Pay", "Explore Jobs"]
)

# --- Overview -----------------------------------------------------------
with tab_overview:
    remote_share = filtered["remote"].mean() * 100

    tiles = "".join(
        [
            stat_tile("Postings", f"{len(filtered):,}", f"of {len(jobs):,} total"),
            stat_tile("Companies hiring", f"{filtered['company'].nunique():,}"),
            stat_tile("Remote share", f"{remote_share:.1f}%", f"{int(filtered['remote'].sum()):,} remote postings"),
            stat_tile("Categories", f"{filtered['category'].nunique():,}", "role / experience types"),
        ]
    )
    st.markdown(f"<div class='stat-grid'>{tiles}</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            section_header("Top categories", "Most common role / experience-level tags")
            counts = filtered["category"].value_counts().rename_axis("category").reset_index(name="postings")
            st.altair_chart(ranked_bar(counts, "category", "postings", BLUE), width="stretch")

    with col2:
        with st.container(border=True):
            section_header("Top companies hiring", "By number of open postings")
            counts = filtered["company"].value_counts().rename_axis("company").reset_index(name="postings")
            st.altair_chart(ranked_bar(counts, "company", "postings", AQUA), width="stretch")

# --- Trends ---------------------------------------------------------------
with tab_trends:
    with st.container(border=True):
        section_header("Postings per week", "Volume of postings by posted date")
        ts = (
            filtered.dropna(subset=["posted_date"])
            .set_index("posted_date")
            .assign(_n=1)["_n"]
            .resample("W")
            .sum()
            .rename_axis("week")
            .reset_index(name="postings")
        )
        if ts.empty:
            st.info("No dated postings to chart.")
        else:
            line = (
                alt.Chart(ts)
                .mark_line(point=alt.OverlayMarkDef(size=45, color=BLUE), strokeWidth=2, color=BLUE)
                .encode(
                    x=alt.X("week:T", title=None),
                    y=alt.Y("postings:Q", title="Postings"),
                    tooltip=[alt.Tooltip("week:T", title="Week of"), alt.Tooltip("postings:Q", title="Postings")],
                )
            )
            st.altair_chart(styled(line, height=340), width="stretch")

    with st.container(border=True):
        section_header("Weekly postings by source", "Same trend, split by where the posting came from")
        ts_src = (
            filtered.dropna(subset=["posted_date"])
            .assign(week=filtered["posted_date"].dt.to_period("W").dt.start_time)
            .groupby(["week", "source"])
            .size()
            .rename("postings")
            .reset_index()
        )
        if ts_src.empty:
            st.info("No dated postings to chart.")
        else:
            src_order = sorted(ts_src["source"].unique())
            palette = [BLUE, AQUA, VIOLET, ORANGE][: len(src_order)]
            line = (
                alt.Chart(ts_src)
                .mark_line(point=alt.OverlayMarkDef(size=35), strokeWidth=2)
                .encode(
                    x=alt.X("week:T", title=None),
                    y=alt.Y("postings:Q", title="Postings"),
                    color=alt.Color("source:N", title=None, scale=alt.Scale(domain=src_order, range=palette)),
                    tooltip=["week:T", "source:N", "postings:Q"],
                )
            )
            st.altair_chart(styled(line, height=340), width="stretch")

# --- Skills -----------------------------------------------------------------
with tab_skills:
    skills_flat = explode_list_col(filtered["skills"])

    if skills_flat.empty:
        st.info("No skills tagged for the current filter selection.")
    else:
        top_skill = skills_flat.value_counts().index[0]
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(stat_tile("Distinct skills tracked", f"{skills_flat.nunique():,}"), unsafe_allow_html=True)
        with col2:
            st.markdown(stat_tile("Most in-demand", top_skill.title()), unsafe_allow_html=True)
        with col3:
            avg_per_posting = filtered["skills"].map(lambda v: len(v) if hasattr(v, "__len__") else 0).mean()
            st.markdown(stat_tile("Avg. skills / posting", f"{avg_per_posting:.1f}"), unsafe_allow_html=True)

        st.write("")
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                section_header("Most-demanded skills", "Share of postings mentioning each skill")
                counts = skills_flat.value_counts().rename_axis("skill").reset_index(name="postings")
                st.altair_chart(ranked_bar(counts, "skill", "postings", BLUE, n=15), width="stretch")

        with col2:
            with st.container(border=True):
                section_header("Skills that pair together", "Top skill combinations within the same posting")
                pair_counts: Counter[tuple[str, str]] = Counter()
                for row in filtered["skills"].dropna():
                    uniq = sorted({str(s).strip() for s in row if str(s).strip()})
                    for a, b in itertools.combinations(uniq, 2):
                        pair_counts[(a, b)] += 1
                if not pair_counts:
                    st.info("Not enough overlapping skills to pair yet.")
                else:
                    pairs_df = pd.DataFrame(
                        [{"pair": f"{a} + {b}", "postings": n} for (a, b), n in pair_counts.most_common(10)]
                    )
                    st.altair_chart(ranked_bar(pairs_df, "pair", "postings", VIOLET, n=10), width="stretch")

# --- Location & Pay ----------------------------------------------------------
with tab_pay:
    col1, col2 = st.columns([1, 1.4])
    with col1:
        with st.container(border=True):
            section_header("Remote vs. on-site")
            remote_n = int(filtered["remote"].sum())
            onsite_n = len(filtered) - remote_n
            total = max(len(filtered), 1)
            segments = [
                ("On-site", onsite_n / total * 100, BLUE),
                ("Remote", remote_n / total * 100, AQUA),
            ]
            st.markdown(proportion_bar(segments), unsafe_allow_html=True)

    with col2:
        with st.container(border=True):
            section_header("Top locations", "Where postings are based")
            counts = filtered["location"].value_counts().rename_axis("location").reset_index(name="postings")
            st.altair_chart(ranked_bar(counts, "location", "postings", ORANGE, n=8), width="stretch")

    with st.container(border=True):
        section_header(
            "Reported salary ranges",
            "Free-text ranges as posted by each source — mixes hourly and annual pay, shown as reported rather than normalized.",
        )
        salary_vals = filtered["salary"].astype(str).str.strip()
        salary_vals = salary_vals[(salary_vals != "") & (salary_vals.str.lower() != "nan")]
        if salary_vals.empty:
            st.info("No salary information reported for the current filter selection.")
        else:
            counts = salary_vals.value_counts().rename_axis("salary").reset_index(name="postings")
            st.altair_chart(ranked_bar(counts, "salary", "postings", AQUA, n=10), width="stretch")

# --- Explore ------------------------------------------------------------
with tab_explore:
    section_header("Browse postings", f"{len(filtered):,} rows match your filters")

    display_cols = ["title", "company", "location", "remote", "category", "source", "posted_date", "salary", "url"]
    view = filtered[display_cols].copy()
    view["remote"] = view["remote"].map({True: "Remote", False: "On-site"})
    view = view.sort_values("posted_date", ascending=False)

    st.dataframe(
        view,
        width="stretch",
        height=460,
        hide_index=True,
        column_config={
            "title": st.column_config.TextColumn("Title", width="medium"),
            "company": st.column_config.TextColumn("Company"),
            "location": st.column_config.TextColumn("Location"),
            "remote": st.column_config.TextColumn("Work type"),
            "category": st.column_config.TextColumn("Category"),
            "source": st.column_config.TextColumn("Source"),
            "posted_date": st.column_config.DateColumn("Posted", format="MMM D, YYYY"),
            "salary": st.column_config.TextColumn("Salary (as reported)"),
            "url": st.column_config.LinkColumn("Listing", display_text="Open ↗"),
        },
    )

    st.download_button(
        "Download filtered CSV",
        filtered.drop(columns=["skills", "tags"]).to_csv(index=False).encode("utf-8"),
        file_name="job_market_filtered.csv",
        mime="text/csv",
    )

# ----------------------------------------------------------------------------
# Footer
# ----------------------------------------------------------------------------
with st.expander("About this dashboard"):
    st.markdown(
        f"""
        Postings are collected daily from **Remotive**, **Arbeitnow**, and **WeWorkRemotely**,
        landed untouched as **bronze** Parquet, deduplicated and skill-tagged into a single
        **silver** table, then aggregated into **gold** mart tables for fast querying —
        all in DuckDB, no cloud warehouse required.

        Source code: [{REPO_URL.replace("https://", "")}]({REPO_URL})
        """
    )

st.markdown(
    f"<div class='footer-note'>Job Market Intelligence · data refreshed {span_end:%B %d, %Y} · "
    f"built with Streamlit, DuckDB &amp; Altair</div>",
    unsafe_allow_html=True,
)
