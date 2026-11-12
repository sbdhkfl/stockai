// Typed client for the FAIRVALUE REST API. All dashboard data comes from the
// running API (docs/ARCHITECTURE.md §7). No fake or decorative data anywhere.

export const API_BASE =
  process.env.NEXT_PUBLIC_FAIRVALUE_API ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  code: string;
  detail?: string;
  constructor(code: string, message: string, detail?: string) {
    super(`[${code}] ${message}`);
    this.code = code;
    this.detail = detail;
  }
}

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, API_BASE);
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const res = await fetch(url.toString(), { cache: "no-store" });
  const body = await res.json().catch(() => null);
  if (!res.ok || (body && body.error)) {
    const err = body?.error ?? {};
    throw new ApiError(err.code ?? `http_${res.status}`, err.message ?? res.statusText, err.detail);
  }
  return body as T;
}

export interface CompanyProfile {
  ticker: string; name: string; sector?: string | null; industry?: string | null;
  is_illustrative?: boolean; [k: string]: unknown;
}
export interface ModelResult {
  model: string; applicable: boolean; value_per_share?: number | null;
  enterprise_value?: number | null; equity_value?: number | null;
  confidence?: string; suitability?: number;
  assumptions?: Record<string, unknown>; formula?: string;
  steps?: string[]; limitations?: string[]; warnings?: string[];
  excluded_reason?: string | null;
}
export interface Report {
  schema_version: string; report_id?: string | null; generated_at: string;
  company: CompanyProfile; market?: { price?: number | null; is_illustrative?: boolean } | null;
  models: ModelResult[];
  reconciliation: { included: string[]; excluded: { model: string; reason: string }[];
    family_values: Record<string, number>; low: number | null; base: number | null;
    high: number | null; method: string; notes: string[] };
  scenarios?: {
    bear: { name: string; value_per_share: number | null; applied_assumptions: Record<string, unknown>; notes: string[] };
    base: { name: string; value_per_share: number | null; applied_assumptions: Record<string, unknown>; notes: string[] };
    bull: { name: string; value_per_share: number | null; applied_assumptions: Record<string, unknown>; notes: string[] };
    sensitivity: { wacc: number; terminal_growth: number; value_per_share: number | null }[];
  } | null;
  health?: Record<string, number | null>; multiples?: Record<string, number | null>;
  growth?: { revenue_cagr?: number | null; [k: string]: unknown } | null;
  risks?: { altman_z: number | null; altman_zone: string | null; leverage_notes: string[];
    consecutive_fcf_negative: number; flags: string[]; data_gaps: string[] };
  explanation?: { headline: string; methodology: string; key_assumptions: string[];
    missing_data: string[]; what_would_invalidate: string[]; risks: string[]; is_illustrative: boolean };
  data_quality: { missing: string[]; conflicts: string[]; warnings: string[]; sources: unknown[] };
  is_illustrative: boolean;
}

export const api = {
  search: (q: string, demo = false) =>
    get<CompanyProfile[]>("/v1/companies/search", { q, demo: String(demo) }),
  company: (ticker: string, demo = false) =>
    get<CompanyProfile>(`/v1/companies/${ticker}`, { demo: String(demo) }),
  valuation: (ticker: string, demo = false) =>
    get<Report>(`/v1/companies/${ticker}/valuation`, { demo: String(demo) }),
  health: (ticker: string, demo = false) =>
    get<Record<string, number | null>>(`/v1/companies/${ticker}/health`, { demo: String(demo) }),
  risks: (ticker: string, demo = false) =>
    get<Report["risks"]>(`/v1/companies/${ticker}/risks`, { demo: String(demo) }),
  statements: (ticker: string, demo = false) =>
    get<FundamentalsResponse>(`/v1/companies/${ticker}/statements`, { demo: String(demo) }),
  reports: () => get<{ report_id: string; ticker: string; generated_at: string }[]>(
    "/v1/reports"),
};

export interface FundamentalsResponse {
  company: CompanyProfile;
  periods: { fiscal_year: number; period_end: string; facts: Record<string, {
    value: number; unit: string; form?: string; accession?: string; filed_at?: string;
    source: { provider: string; locator?: string };
  }> };
  missing_concepts: string[]; conflicts: string[]; validation_errors?: string[];
}
