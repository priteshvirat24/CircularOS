const API_ORIGIN = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_URL = `${API_ORIGIN.replace(/\/$/, "")}/api/v1`;

let accessToken: string | null = null;

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  user: { id: string; email: string; full_name: string };
  organization: { id: string; name: string; slug: string } | null;
};

export type Verification = {
  route: string | null;
  citation_checks: Array<{ match_type?: string; valid?: boolean; cited_text?: string; source_span?: string }>;
  entailment: { thresholded?: string; raw?: { reasoning?: string; label?: string } };
  critic: { has_substantive_objection?: boolean; objection?: string; reasoning?: string } | null;
  confidence: { score?: number; band?: string; factors?: string[] };
  confidence_factors: string[];
};

export type Obligation = {
  id: string; document_id: string; normalized_obligation: string; actor: string | null;
  action: string | null; object: string | null; deadline_description: string | null;
  risk_level: string | null; status: string; review_status: string | null; confidence: number | null;
  updated_at: string | null; verification: Verification; source_text?: string;
  citations?: Array<{ id: string; field_name: string; cited_text: string; page_number: number | null; char_start: number | null; char_end: number | null; confidence: number | null }>;
};

export type PaginatedObligations = { obligations: Obligation[]; total: number; page: number; page_size: number };
export type ObligationSummary = { total: number; status_counts: Record<string, number>; citation_verification: { verified: number; checked: number; rate: number | null } };
export type Document = { id: string; title: string; reference_number: string | null; document_type: string | null; regulatory_domain: string | null; status: string; issued_date: string | null; page_count: number | null; parsing_quality_score: number | null; created_at: string };
export type DocumentsResponse = { documents: Document[]; total: number; page: number; page_size: number };
export type Change = { id: string; change_type: string; obligation: string | null; changed_fields: string[]; old_ref: string | null; new_ref: string | null; old_text: string | null; new_text: string | null; materiality: string | null; materiality_reasons: string[]; confidence: number | null; requires_confirmation: boolean; citations: Record<string, unknown> };
export type Diff = { diff_run_id: string; status: string; old_document: { id: string; title: string | null }; new_document: { id: string; title: string | null }; summary: Record<string, number> | null; changes: Change[] };
export type Control = { id: string; name: string; description: string | null; control_type: string | null; department: string | null; status: string; framework: string | null; mapped_obligations: number; source_topic: string | null };
export type Evidence = { id: string; file_name: string; evidence_type: string | null; status: string; freshness_state: string | null; obligation_id: string | null; collection_date: string | null; valid_until: string | null };
export type AgentRun = { id: string; document_id: string; workflow_type: string; status: string; current_stage: string | null; total_obligations: number | null; total_tokens: number | null; total_cost_usd: number | null; duration_seconds: number | null; completed_at: string | null };
export type Review = { id: string; task_type: string; priority: string; status: string; obligation_id: string | null; context: Record<string, unknown> | null; created_at: string; obligation?: Obligation | null };
export type Posture = { latest_circular: { circular_id: string; title: string | null; tracked_changes: number }; market_rollup: { intermediaries: number; real_intermediaries: number; seeded_intermediaries: number; coverage_percentage: number; open_gaps: number; latest_circular_adoption_percentage: number }; intermediaries: Array<{ intermediary_id: string; name: string; seeded: boolean; coverage: { percentage: number; applicable_obligations: number; covered_obligations: number }; evidence_freshness: Record<string, number>; open_gaps: { total: number; by_severity: Record<string, number> }; latest_circular_adoption: { percentage: number; operationalized: number; tracked_changes: number } }> };
export type Evaluation = { evaluation_run_id: string; headline_metrics: { f1: number | null; detection_rate: number | null; false_positive_rate: number | null }; bootstrap_f1_95_ci: [number, number] | null; field_accuracy: Record<string, number> | null; difficulty_breakdown: Record<string, unknown> | null; named_failures: Array<Record<string, unknown>>; matcher_config: Record<string, unknown> | null; calibrated_routing_split: Record<string, number> | null; verification_provenance: Record<string, unknown> | null };
export type PublicDashboard = { documents: Array<{ id: string; title: string; reference_number: string | null; status: string; page_count: number | null }>; obligation_total: number; diff_change_total: number | null; diff_summary: Record<string, number> | null; evaluation_f1: number | null; evaluation_ci: { lower?: number; upper?: number } | null };

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new ApiError(response.status, body?.detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

async function upload(path: string, file: File): Promise<{ document_id: string; status: string }> {
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const form = new FormData();
  form.set("file", file);
  form.set("title", file.name);
  const response = await fetch(`${API_URL}${path}`, { method: "POST", headers, body: form });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new ApiError(response.status, body?.detail || `Upload failed (${response.status})`);
  }
  return response.json() as Promise<{ document_id: string; status: string }>;
}

export const api = {
  setAccessToken(token: string | null) { accessToken = token; },
  dashboard: () => request<PublicDashboard>("/dashboard"),
  login(email: string, password: string) { return request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }); },
  documents: () => request<DocumentsResponse>("/documents?page=1&page_size=50"),
  uploadDocument: (file: File) => upload("/documents/ingest/upload", file),
  obligations: (page: number, search = "", status = "", documentId = "") => request<PaginatedObligations>(`/obligations?page=${page}&page_size=50${search ? `&search=${encodeURIComponent(search)}` : ""}${status ? `&status=${encodeURIComponent(status)}` : ""}${documentId ? `&document_id=${encodeURIComponent(documentId)}` : ""}`),
  obligationSummary: (documentId = "") => request<ObligationSummary>(`/obligations/summary${documentId ? `?document_id=${encodeURIComponent(documentId)}` : ""}`),
  obligation: (id: string) => request<Obligation>(`/obligations/${id}`),
  diffRuns: () => request<{ diff_runs: Array<{ diff_run_id: string }>; total: number }>("/diff?limit=1"),
  diff: (id: string) => request<Diff>(`/diff/${id}`),
  controls: () => request<{ controls: Control[]; total: number }>("/controls"),
  evidence: () => request<{ evidence: Evidence[]; total: number }>("/evidence?page=1&page_size=10"),
  runs: () => request<{ runs: AgentRun[]; total: number }>("/agents/runs?page=1&page_size=20"),
  reviews: () => request<{ reviews: Review[]; total: number }>("/reviews?page=1&page_size=50&status=pending"),
  decideReview: (id: string, action: "approve" | "reject") => request(`/reviews/${id}/decision`, { method: "POST", body: JSON.stringify({ action }) }),
  posture: () => request<Posture>("/suptech/posture"),
  adoption: (id: string) => request<Record<string, unknown>>(`/suptech/adoption/${id}`),
  gap: (key: string) => request<Record<string, unknown>>(`/suptech/gaps/${encodeURIComponent(key)}`),
  latestEvaluation: (runType?: string) => request<Evaluation>(`/evaluation/runs/latest${runType ? `?run_type=${encodeURIComponent(runType)}` : ""}`),
};
