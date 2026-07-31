"""Business logic for analysis jobs and evidence creation.

This module separates domain logic from views, making it testable and
reusable from both synchronous views and async Celery tasks.
"""

import hashlib
import random
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from apps.ledger.models import AnalysisJob, Claim, Evidence, Thesis

if TYPE_CHECKING:
    from collections.abc import Sequence


def compute_cache_key(thesis: Thesis) -> str:
    """SHA-256 hash of thesis text + company ticker for cache-aside."""
    content = f"{thesis.text}:{thesis.company.ticker}"
    return hashlib.sha256(content.encode()).hexdigest()


def create_analysis_job(thesis: Thesis) -> AnalysisJob:
    """Create a new pending AnalysisJob for the given thesis."""
    approved_claims = thesis.claims.filter(is_approved=True)
    cache_key = compute_cache_key(thesis)

    job = AnalysisJob.objects.create(
        thesis=thesis,
        status=AnalysisJob.Status.PENDING,
        total_claims=approved_claims.count(),
        cache_key=cache_key,
    )
    return job


def start_job(job: AnalysisJob) -> None:
    """Mark job as running with start timestamp."""
    job.status = AnalysisJob.Status.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at", "updated_at"])


def complete_job(job: AnalysisJob) -> None:
    """Mark job as done with finish timestamp."""
    job.status = AnalysisJob.Status.DONE
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "finished_at", "updated_at"])


def fail_job(job: AnalysisJob, error: str) -> None:
    """Mark job as failed with error message."""
    job.status = AnalysisJob.Status.FAILED
    job.error = error
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "error", "finished_at", "updated_at"])


def update_job_progress(job: AnalysisJob, progress: int) -> None:
    """Update progress counter (claims processed so far)."""
    job.progress = progress
    job.save(update_fields=["progress", "updated_at"])


def write_mock_evidence(job: AnalysisJob, claims: "Sequence[Claim]") -> None:
    """Write mock Evidence rows for testing before real AI is wired.

    Creates one Evidence per claim with random status. Used during Day 1
    development before LangGraph pipeline is ready.
    """
    statuses = [
        Evidence.Status.SUPPORTED,
        Evidence.Status.CONTRADICTED,
        Evidence.Status.INSUFFICIENT,
    ]
    explanations = {
        Evidence.Status.SUPPORTED: "The filing supports this claim based on reported figures.",
        Evidence.Status.CONTRADICTED: "The filing data contradicts this claim.",
        Evidence.Status.INSUFFICIENT: "No relevant passage found in retrieved chunks.",
    }
    quotes = {
        Evidence.Status.SUPPORTED: "Revenue increased 15% year over year.",
        Evidence.Status.CONTRADICTED: "Margins declined compared to prior period.",
        Evidence.Status.INSUFFICIENT: "",
    }

    for i, claim in enumerate(claims):
        status = random.choice(statuses)
        Evidence.objects.create(
            job=job,
            claim=claim,
            status=status,
            explanation=explanations[status],
            quote=quotes[status],
            chunk=None,
            similarity=round(random.uniform(0.6, 0.9), 2) if status != Evidence.Status.INSUFFICIENT else None,
        )
        update_job_progress(job, i + 1)


def run_mock_analysis(job: AnalysisJob) -> None:
    """Execute mock analysis flow for Day 1 testing.

    This will be replaced by run_real_analysis() once LangGraph is wired.
    """
    try:
        start_job(job)
        claims = list(job.thesis.claims.filter(is_approved=True))
        write_mock_evidence(job, claims)
        complete_job(job)
    except Exception as e:
        fail_job(job, str(e))
        raise


def run_real_analysis(job: AnalysisJob) -> None:
    """Execute real analysis using LangGraph pipeline.

    Runs claim extraction and classification against SEC filings.
    Creates Evidence records for each claim.
    """
    from apps.ledger.models import Chunk
    from apps.rag.graph import run_analysis

    try:
        start_job(job)

        thesis = job.thesis
        company = thesis.company

        # Run the LangGraph pipeline
        results = run_analysis(
            thesis_id=str(thesis.id),
            thesis_text=thesis.text,
            company_id=str(company.id),
            company_ticker=company.ticker,
        )

        # Get approved claims to match with results
        claims = list(thesis.claims.filter(is_approved=True).order_by("ordinal"))

        # Create Evidence records from results
        for i, result in enumerate(results):
            claim = claims[i] if i < len(claims) else None
            if not claim:
                continue

            chunk = None
            if result.get("chunk_id"):
                chunk = Chunk.objects.filter(id=result["chunk_id"]).first()

            Evidence.objects.create(
                job=job,
                claim=claim,
                status=result["status"],
                explanation=result["explanation"],
                quote=result.get("quote", ""),
                chunk=chunk,
                similarity=result.get("similarity"),
            )
            update_job_progress(job, i + 1)

        complete_job(job)

    except Exception as e:
        fail_job(job, str(e))
        raise


def write_claims(thesis: Thesis) -> list[Claim]:
    """Generate claims for a thesis and replace any existing ones.

    Shared by the Celery task and the inline fallback, so both paths leave the
    thesis in the same state.
    """
    from apps.ledger.claim_generation import generate_claims

    texts = generate_claims(thesis)[: Claim.MAX_PER_THESIS]

    with transaction.atomic():
        thesis.claims.all().delete()
        claims = Claim.objects.bulk_create(
            [
                Claim(thesis=thesis, ordinal=ordinal, text=text, origin=Claim.Origin.LLM)
                for ordinal, text in enumerate(texts)
            ]
        )
        thesis.status = Thesis.Status.CLAIMS_GENERATED
        thesis.save(update_fields=["status", "updated_at"])

    return claims
