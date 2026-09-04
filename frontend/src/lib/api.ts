const BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError("Could not reach the API gateway. Is the platform running?");
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
};

export interface GatewayHealth {
  gateway: string;
  services: Record<string, { status: string }>;
}

export interface Connector {
  id: string;
  name: string;
  source_type: "database" | "api" | "flat_file";
  department: string;
  refresh_mode: string;
  status: "draft" | "active" | "paused";
  created_at: string;
}

export interface GoldenRecord {
  id: string;
  attributes: Record<string, string>;
  contributing_sources: string[];
  classification: string;
  created_at: string;
  updated_at: string;
}

export interface DoubtRecord {
  id: string;
  attributes: Record<string, string>;
  contributing_sources: string[];
  classification: string;
  candidate_matches: { golden_record_id?: string; doubt_record_id?: string; score: number; evidence: string }[];
  status: "open" | "resolved";
  created_at: string;
  resolved_by?: string;
  resolution?: string;
}

export interface ConsentRecord {
  id: string;
  data_principal_id: string;
  purpose_id: string;
  status: "granted" | "revoked" | "expired";
  collection_channel: string;
  granted_by: string;
  granted_at: string;
  revoked_at?: string;
}

export interface SchemeRule {
  id: string;
  scheme_code: string;
  name: string;
  eligibility_conditions: { field: string; op: string; value: number }[];
  exclusion_conditions: { field: string; op: string; value: number }[];
}

export interface SyncRun {
  id: string;
  trigger_type: string;
  triggered_by: string;
  status: "queued" | "running" | "succeeded" | "failed";
  beneficiaries_submitted: number;
  beneficiaries_synced: number;
  error?: string;
  started_at: string;
  completed_at?: string;
}
