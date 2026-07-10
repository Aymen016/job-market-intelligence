const BASE = "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export interface Summary {
  total_jobs: number;
  sources: number;
  remote_pct: number;
  top_skill: string;
  last_ingest_date: string;
}

export interface SkillDemand {
  skill: string;
  job_count: number;
  pct_of_total: number;
}

export interface RemoteSplit {
  work_type: string;
  job_count: number;
  pct: number;
}

export interface TopCategory {
  category: string;
  job_count: number;
}

export interface SalarySample {
  source: string;
  salary: string;
  count: number;
}

export interface DailyVolume {
  ingest_date: string;
  source: string;
  job_count: number;
}

export interface SkillPair {
  skill_a: string;
  skill_b: string;
  co_occurrences: number;
}

export interface TopCompany {
  company: string;
  openings: number;
}

export interface SourceBreakdown {
  source: string;
  job_count: number;
  pct: number;
}

export interface TrendPoint {
  week_start: string;
  job_count: number;
}

export const api = {
  summary: () => get<Summary>("/api/summary"),
  skillDemand: (limit = 20) => get<SkillDemand[]>(`/api/skill-demand?limit=${limit}`),
  remoteSplit: () => get<RemoteSplit[]>("/api/remote-split"),
  topCategories: (limit = 12) => get<TopCategory[]>(`/api/top-categories?limit=${limit}`),
  salarySamples: (limit = 50) => get<SalarySample[]>(`/api/salary-samples?limit=${limit}`),
  dailyVolume: () => get<DailyVolume[]>("/api/daily-volume"),
  skillCooccurrence: (limit = 15) => get<SkillPair[]>(`/api/skill-cooccurrence?limit=${limit}`),
  topCompanies: (limit = 12) => get<TopCompany[]>(`/api/top-companies?limit=${limit}`),
  sourceBreakdown: () => get<SourceBreakdown[]>("/api/source-breakdown"),
  skillTrend: (skill: string) => get<TrendPoint[]>(`/api/skill-trend?skill=${encodeURIComponent(skill)}`),
};
