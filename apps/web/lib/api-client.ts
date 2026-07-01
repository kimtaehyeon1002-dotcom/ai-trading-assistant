// 백엔드 REST 클라이언트. 액세스 토큰은 localStorage, 만료 시 refresh.
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";
// SSE stream_url(서버가 /api/v1 포함 절대경로로 반환)에 붙일 오리진.
export const API_ORIGIN = BASE.replace(/\/api\/v1\/?$/, "");

type Tokens = { access_token: string; refresh_token: string; expires_in: number };

function getAccess(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}
function getRefresh(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}
function setTokens(t: Tokens) {
  localStorage.setItem("access_token", t.access_token);
  localStorage.setItem("refresh_token", t.refresh_token);
}
export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

async function refresh(): Promise<boolean> {
  const rt = getRefresh();
  if (!rt) return false;
  const res = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: rt }),
  });
  if (!res.ok) return false;
  setTokens((await res.json()) as Tokens);
  return true;
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const access = getAccess();
  if (access) headers.set("Authorization", `Bearer ${access}`);

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401 && retry && (await refresh())) {
    return api<T>(path, init, false);
  }
  if (!res.ok) {
    const problem = await res.json().catch(() => ({}));
    throw new Error(problem.detail || problem.title || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("로그인 실패");
  setTokens((await res.json()) as Tokens);
}

export const me = () => api<{ email: string; role: string; investment_styles: string[] }>("/auth/me");
export const getQuote = (instrumentId: number) => api<any>(`/market/quotes/${instrumentId}`);
export const searchSymbols = (q: string) => api<{ data: any[] }>(`/market/symbols?q=${encodeURIComponent(q)}`);

export type JobEnvelope = { job_id: string; status: string; stream_url: string; result_url: string };
export const createResearchJob = (body: {
  symbol?: string | null;
  instrument_id?: number | null;
  query?: string | null;
  style?: string;
  depth?: string;
}) => api<JobEnvelope>("/research/jobs", { method: "POST", body: JSON.stringify(body) });
export const getResearchResult = (id: string) => api<any>(`/research/results/${id}`);

export const listReports = (limit = 20) => api<any[]>(`/reports?limit=${limit}`);
export const getReportByDate = (date: string, scope = "global") =>
  api<any>(`/reports/by-date/${date}?scope=${scope}`);
export const getThemeScores = (market: string, timeframe = "swing") =>
  api<any[]>(`/reports/themes?market=${market}&timeframe=${timeframe}`);
export const generateReport = (body: { report_date?: string; force?: boolean } = {}) =>
  api<{ report_date: string; scope: string; status: string }>("/reports/generate", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const importJournal = () =>
  api<{ source: string; imported: number; skipped: number; total_seen: number; is_stub: boolean }>(
    "/journal/import",
    { method: "POST" }
  );
export const getJournalEntries = (limit = 200) => api<any[]>(`/journal/entries?limit=${limit}`);
export const getJournalMetrics = () => api<any>("/journal/metrics");
export const coachJournal = (question?: string) =>
  api<any>("/journal/coach", { method: "POST", body: JSON.stringify({ question: question ?? null }) });

export const getHoldings = () => api<any[]>("/portfolio/holdings");
export const addHolding = (body: {
  symbol?: string;
  instrument_id?: number;
  quantity: number;
  avg_cost?: number;
}) => api<any>("/portfolio/holdings", { method: "POST", body: JSON.stringify(body) });
export const deleteHolding = (id: string) =>
  api<{ ok: boolean }>(`/portfolio/holdings/${id}`, { method: "DELETE" });
export const getPortfolioMetrics = () => api<any>("/portfolio/metrics");
export const analyzePortfolio = () => api<any>("/portfolio/analyze", { method: "POST" });
