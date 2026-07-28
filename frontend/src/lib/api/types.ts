// Shapes mirror docs/api_contract.md and backend/apps/ledger/{models,serializers}.py.

export type ThesisStatus = "draft" | "claims_generated" | "approved" | "analyzed";
export type ClaimOrigin = "llm" | "user";
export type EvidenceStatus = "supported" | "contradicted" | "insufficient_evidence";
export type JobStatus = "pending" | "running" | "done" | "failed";
export type FilingType = "10-K" | "10-Q";

export interface Company {
  id: string;
  ticker: string;
  name: string;
  cik: string;
  filing_count: number;
}

export interface CompanyBrief {
  id: string;
  ticker: string;
  name: string;
}

export interface Claim {
  id: string;
  ordinal: number;
  text: string;
  origin: ClaimOrigin;
  is_approved: boolean;
}

export interface Thesis {
  id: string;
  company: CompanyBrief;
  text: string;
  status: ThesisStatus;
  claims: Claim[];
  created_at: string;
}

export interface EvidenceSource {
  chunk_id: string;
  section: string;
  filing_type: FilingType;
  period_end: string;
  filed_at: string;
  source_url: string;
}

export interface Evidence {
  id: string;
  status: EvidenceStatus;
  explanation: string;
  quote: string;
  similarity: number | null;
  source: EvidenceSource | null;
}

export interface ClaimSummary {
  id: string;
  ordinal: number;
  text: string;
}

export interface ClaimResult {
  claim: ClaimSummary;
  evidence: Evidence;
}

export interface AnalysisJob {
  id: string;
  thesis_id: string;
  status: JobStatus;
  progress: number;
  total_claims: number;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  results: ClaimResult[];
}

export interface CompanyListResponse {
  results: Company[];
}

export interface GenerateClaimsResponse {
  thesis_id: string;
  status: ThesisStatus;
  claims: Claim[];
}

export interface ApproveClaimsResponse {
  thesis_id: string;
  status: ThesisStatus;
  approved_claim_ids: string[];
}

export interface AnalyzeResponse {
  job_id: string;
  status: JobStatus;
  thesis_id: string;
  total_claims: number;
}

export type ApiErrorCode =
  | "validation_error"
  | "not_found"
  | "conflict"
  | "llm_error"
  | "internal_error";

export interface ApiErrorEnvelope {
  error: {
    code: ApiErrorCode | string;
    message: string;
    field: string | null;
  };
}
