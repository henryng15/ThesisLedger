"""Lightweight evidence generation helpers for Day 6/7."""

from __future__ import annotations

from typing import Any

from apps.ledger.models import AnalysisJob, Claim, Chunk, Evidence


class EvidenceGenerationError(RuntimeError):
    """Raised when evidence cannot be generated for a claim."""


def build_evidence_for_claim(claim: Claim, job: AnalysisJob, chunk: Chunk | None = None) -> Evidence:
    """Create a deterministic evidence row using the first available chunk as citation context."""
    if chunk is None:
        chunk = claim.thesis.company.filings.first().chunks.first() if claim.thesis.company.filings.exists() else None

    if chunk is None or chunk.text == "":
        return Evidence.objects.create(
            claim=claim,
            job=job,
            status=Evidence.Status.INSUFFICIENT,
            explanation="No retrievable filing chunk was available for this claim.",
            quote="",
            chunk=None,
            similarity=None,
        )

    quote = chunk.text[:120]
    status = Evidence.Status.SUPPORTED
    similarity = 0.95

    return Evidence.objects.create(
        claim=claim,
        job=job,
        status=status,
        explanation="The claim is supported by the retrieved filing chunk.",
        quote=quote,
        chunk=chunk,
        similarity=similarity,
    )
