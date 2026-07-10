import { useEffect, useState } from "react";
import "./App.css";
import { api } from "./api";
import type {
  DailyVolume,
  RemoteSplit,
  SalarySample,
  SkillDemand,
  SkillPair,
  SourceBreakdown,
  Summary,
  TopCategory,
  TopCompany,
} from "./api";
import { Card } from "./components/Card";
import { StatTile } from "./components/StatTile";
import { BarList } from "./components/BarList";
import { SplitBar } from "./components/SplitBar";
import { TrendChart } from "./components/TrendChart";
import { DataTable } from "./components/DataTable";
import type { Column } from "./components/DataTable";
import type { TrendSeries } from "./components/TrendChart";

type Theme = "light" | "dark";

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  return [theme, () => setTheme((t) => (t === "light" ? "dark" : "light"))];
}

interface DashboardData {
  summary: Summary;
  skillDemand: SkillDemand[];
  remoteSplit: RemoteSplit[];
  topCategories: TopCategory[];
  salarySamples: SalarySample[];
  dailyVolume: DailyVolume[];
  skillCooccurrence: SkillPair[];
  topCompanies: TopCompany[];
  sourceBreakdown: SourceBreakdown[];
}

const SOURCE_COLORS: Record<string, string> = {
  arbeitnow: "var(--series-1)",
  remotive: "var(--series-2)",
  weworkremotely: "var(--series-3)",
};

const SALARY_COLUMNS: Column<SalarySample>[] = [
  { key: "source", label: "Source" },
  { key: "salary", label: "Salary" },
  { key: "count", label: "Count", align: "right", tabular: true },
];

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.summary(),
      api.skillDemand(20),
      api.remoteSplit(),
      api.topCategories(12),
      api.salarySamples(40),
      api.dailyVolume(),
      api.skillCooccurrence(14),
      api.topCompanies(12),
      api.sourceBreakdown(),
    ])
      .then(
        ([
          summary,
          skillDemand,
          remoteSplit,
          topCategories,
          salarySamples,
          dailyVolume,
          skillCooccurrence,
          topCompanies,
          sourceBreakdown,
        ]) =>
          setData({
            summary,
            skillDemand,
            remoteSplit,
            topCategories,
            salarySamples,
            dailyVolume,
            skillCooccurrence,
            topCompanies,
            sourceBreakdown,
          })
      )
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="state-screen">
        <p className="state-screen__title">Couldn't reach the data.</p>
        <p className="state-screen__body">
          Make sure the API is running (<code>uvicorn backend.main:app</code>) and that the
          pipeline has produced data (<code>python -m flows.daily_flow</code>).
        </p>
        <p className="state-screen__detail tabular">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="state-screen">
        <p className="state-screen__title">Loading…</p>
      </div>
    );
  }

  const remoteColor: Record<string, string> = {
    Remote: "var(--series-2)",
    "On-site": "var(--series-1)",
  };

  const trendSeries: TrendSeries[] = Object.values(
    data.dailyVolume.reduce<Record<string, TrendSeries>>((acc, row) => {
      const key = row.source;
      if (!acc[key]) {
        acc[key] = { name: key, color: SOURCE_COLORS[key] ?? "var(--series-4)", points: [] };
      }
      acc[key].points.push({ x: row.ingest_date, y: row.job_count });
      return acc;
    }, {})
  );

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1 className="app-header__title">Job Market Observatory</h1>
          <p className="app-header__subtitle">
            {data.summary.total_jobs.toLocaleString()} open postings across{" "}
            {data.summary.sources} sources · last refreshed {formatDate(data.summary.last_ingest_date)}
          </p>
        </div>
        <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
          {theme === "light" ? "🌙 Dark" : "☀️ Light"}
        </button>
      </header>

      <div className="kpi-row">
        <StatTile label="Open postings" value={data.summary.total_jobs.toLocaleString()} accent />
        <StatTile label="Remote share" value={`${data.summary.remote_pct}%`} />
        <StatTile label="Sources tracked" value={String(data.summary.sources)} />
        <StatTile label="Most in-demand skill" value={data.summary.top_skill} />
      </div>

      <div className="dashboard-grid">
        <Card title="Top skills" subtitle="Most-mentioned skills across all postings" span="full">
          <BarList
            items={data.skillDemand.map((s) => ({
              label: s.skill,
              value: s.job_count,
              detail: `${s.pct_of_total}% of all postings`,
            }))}
          />
        </Card>

        <Card title="Remote vs on-site" subtitle="Share of postings by work type">
          <SplitBar
            segments={data.remoteSplit.map((r) => ({
              label: r.work_type,
              value: r.job_count,
              pct: r.pct,
              color: remoteColor[r.work_type] ?? "var(--series-3)",
            }))}
          />
        </Card>

        <Card title="Postings by source" subtitle="Where the listings came from">
          <SplitBar
            segments={data.sourceBreakdown.map((s) => ({
              label: s.source,
              value: s.job_count,
              pct: s.pct,
              color: SOURCE_COLORS[s.source] ?? "var(--series-4)",
            }))}
          />
        </Card>

        <Card title="Top categories" subtitle="Job type / category, as tagged by source">
          <BarList
            color="var(--series-3)"
            items={data.topCategories.map((c) => ({ label: c.category, value: c.job_count }))}
          />
        </Card>

        <Card title="Top hiring companies" subtitle="Most open roles per company">
          <BarList
            color="var(--series-4)"
            items={data.topCompanies.map((c) => ({ label: c.company, value: c.openings }))}
          />
        </Card>

        <Card title="Skills that travel together" subtitle="Most common skill pairs in the same posting" span="full">
          <BarList
            color="var(--series-5)"
            formatValue={(v) => `${v}`}
            items={data.skillCooccurrence.map((p) => ({
              label: `${p.skill_a} + ${p.skill_b}`,
              value: p.co_occurrences,
              detail: `appear together in ${p.co_occurrences} postings`,
            }))}
          />
        </Card>

        <Card
          title="Daily posting volume"
          subtitle="Postings landed per day, by source — fills in as the pipeline runs daily"
          span="full"
        >
          <TrendChart series={trendSeries} />
        </Card>

        <Card title="Disclosed salaries" subtitle="Raw salary text, where a source discloses it" span="full">
          <DataTable columns={SALARY_COLUMNS} rows={data.salarySamples} />
        </Card>
      </div>

      <footer className="app-footer">
        Data pulled from Remotive, Arbeitnow &amp; WeWorkRemotely · refreshed daily by a Prefect
        flow · served from local Parquet files via DuckDB.
      </footer>
    </div>
  );
}
