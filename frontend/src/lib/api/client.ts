import { API_BASE_URL } from "./config";
import { ApiError } from "./errors";
import type {
  AnalysisJob,
  AnalyzeResponse,
  ApiErrorEnvelope,
  ApproveClaimsResponse,
  Claim,
  CompanyListResponse,
  GenerateClaimsResponse,
  Thesis,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      0,
      "internal_error",
      `Unable to reach the ThesisLedger API at ${API_BASE_URL}. Is the backend running?`,
      null,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    const envelope = body as ApiErrorEnvelope | null;
    throw new ApiError(
      response.status,
      envelope?.error.code ?? "internal_error",
      envelope?.error.message ?? "The request failed.",
      envelope?.error.field ?? null,
    );
  }

  return body as T;
}

export const api = {
  listCompanies(): Promise<CompanyListResponse> {
    return request<CompanyListResponse>("/companies/");
  },

  createThesis(payload: { company_id: string; text: string }): Promise<Thesis> {
    return request<Thesis>("/theses/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getThesis(thesisId: string): Promise<Thesis> {
    return request<Thesis>(`/theses/${thesisId}/`);
  },

  generateClaims(thesisId: string, force = false): Promise<GenerateClaimsResponse> {
    return request<GenerateClaimsResponse>(`/theses/${thesisId}/claims:generate`, {
      method: "POST",
      body: JSON.stringify(force ? { force: true } : {}),
    });
  },

  updateClaim(claimId: string, text: string): Promise<Claim> {
    return request<Claim>(`/claims/${claimId}/`, {
      method: "PATCH",
      body: JSON.stringify({ text }),
    });
  },

  deleteClaim(claimId: string): Promise<void> {
    return request<void>(`/claims/${claimId}/`, { method: "DELETE" });
  },

  approveClaims(thesisId: string, claimIds: string[]): Promise<ApproveClaimsResponse> {
    return request<ApproveClaimsResponse>(`/theses/${thesisId}/claims:approve`, {
      method: "POST",
      body: JSON.stringify({ claim_ids: claimIds }),
    });
  },

  analyzeThesis(thesisId: string): Promise<AnalyzeResponse> {
    return request<AnalyzeResponse>(`/theses/${thesisId}/analyze`, { method: "POST" });
  },

  getJob(jobId: string): Promise<AnalysisJob> {
    return request<AnalysisJob>(`/jobs/${jobId}/`);
  },
};
