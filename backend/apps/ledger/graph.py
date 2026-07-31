"""Small graph-like orchestration seam for Day 7."""

from __future__ import annotations

from typing import Any

from apps.ledger.models import AnalysisJob, Claim, Chunk, Evidence, Thesis


class GraphStateError(RuntimeError):
    """Raised when graph state cannot be serialized or executed."""


def build_graph_state(job: AnalysisJob, claims: list[Claim], evidence_rows: list[Evidence]) -> dict[str, Any]:
    """Serialize a simple graph state payload for the job record."""
    return {
        "job_id": str(job.id),
        "thesis_id": str(job.thesis_id),
        "claims": [claim.text for claim in claims],
        "evidence": [
            {
                "claim_id": str(evidence.claim_id),
                "status": evidence.status,
                "quote": evidence.quote,
                "chunk_id": str(evidence.chunk_id) if evidence.chunk_id else None,
            }
            for evidence in evidence_rows
        ],
    }


def run_graph(job: AnalysisJob) -> dict[str, Any]:
    """Create deterministic evidence rows and return graph-state payload."""
    claims = list(job.thesis.claims.filter(is_approved=True))
    evidence_rows: list[Evidence] = []
    for claim in claims:
        chunk = claim.thesis.company.filings.first().chunks.first() if claim.thesis.company.filings.exists() and claim.thesis.company.filings.first().chunks.exists() else None
        evidence_rows.append(build_evidence_for_claim(claim, job, chunk=chunk))

    job.progress = min(len(claims), 100)
    job.total_claims = len(claims)
    job.status = AnalysisJob.Status.DONE
    job.graph_state = build_graph_state(job, claims, evidence_rows)
    job.save(update_fields=["progress", "total_claims", "status", "graph_state", "updated_at"])
    return job.graph_state


def build_evidence_for_claim(claim: Claim, job: AnalysisJob, chunk: Chunk | None = None) -> Evidence:
    from apps.ledger.evidence import build_evidence_for_claim as _build_evidence_for_claim

    return _build_evidence_for_claim(claim, job, chunk=chunk)
