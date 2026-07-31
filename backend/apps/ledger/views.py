"""REST API views for ThesisLedger.

Shapes come from docs/api_contract.md. Thesis and claim endpoints hit the
database. Analysis job endpoints now use real AnalysisJob model.
"""

from django.db import transaction
from django.db.models import Count
from rest_framework import status as http
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.ledger.claim_generation import generate_claims
from apps.ledger.models import AnalysisJob, Claim, Company, Thesis
from apps.ledger.serializers import (
    ClaimApproveSerializer,
    ClaimSerializer,
    ClaimUpdateSerializer,
    CompanySerializer,
    ThesisCreateSerializer,
    ThesisSerializer,
)
from apps.ledger.services import compute_cache_key, create_analysis_job


def api_error(code: str, message: str, status_code: int, field: str | None = None) -> Response:
    """Standard error envelope from the API contract."""
    return Response(
        {"error": {"code": code, "message": message, "field": field}}, status=status_code
    )


def _first_error(serializer) -> tuple[str, str]:
    field, messages = next(iter(serializer.errors.items()))
    return field, str(messages[0])


def _thesis_queryset():
    return Thesis.objects.select_related("company").prefetch_related("claims")


@api_view(["GET"])
def company_list(request: Request) -> Response:
    """List active companies with filing counts."""
    companies = (
        Company.objects.filter(is_active=True)
        .annotate(filing_count=Count("filings"))
        .order_by("ticker")
    )
    return Response({"results": CompanySerializer(companies, many=True).data})


@api_view(["POST"])
def thesis_create(request: Request) -> Response:
    """Create a new thesis for a company."""
    serializer = ThesisCreateSerializer(data=request.data)
    if not serializer.is_valid():
        field, message = _first_error(serializer)
        return api_error("validation_error", message, http.HTTP_400_BAD_REQUEST, field)

    company = Company.objects.filter(
        id=serializer.validated_data["company_id"], is_active=True
    ).first()
    if company is None:
        return api_error(
            "not_found", "No active company with that id.", http.HTTP_404_NOT_FOUND, "company_id"
        )

    thesis = Thesis.objects.create(company=company, text=serializer.validated_data["text"])
    return Response(ThesisSerializer(thesis).data, status=http.HTTP_201_CREATED)


@api_view(["GET"])
def thesis_detail(request: Request, thesis_id: str) -> Response:
    """Get thesis with its claims."""
    thesis = _thesis_queryset().filter(id=thesis_id).first()
    if thesis is None:
        return api_error("not_found", "No thesis with that id.", http.HTTP_404_NOT_FOUND)

    return Response(ThesisSerializer(thesis).data)


@api_view(["POST"])
def claims_generate(request: Request, thesis_id: str) -> Response:
    """Generate claims for a thesis using LLM."""
    thesis = _thesis_queryset().filter(id=thesis_id).first()
    if thesis is None:
        return api_error("not_found", "No thesis with that id.", http.HTTP_404_NOT_FOUND)

    force = bool(request.data.get("force", False)) if isinstance(request.data, dict) else False
    if thesis.claims.exists() and not force:
        return api_error(
            "conflict",
            "Claims already exist for this thesis. Send {\"force\": true} to regenerate.",
            http.HTTP_409_CONFLICT,
        )

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

    return Response(
        {
            "thesis_id": str(thesis.id),
            "status": thesis.status,
            "claims": ClaimSerializer(claims, many=True).data,
        },
        status=http.HTTP_201_CREATED,
    )


@api_view(["PATCH", "DELETE"])
def claim_detail(request: Request, claim_id: str) -> Response:
    """Update or delete a claim."""
    claim = Claim.objects.filter(id=claim_id).first()
    if claim is None:
        return api_error("not_found", "No claim with that id.", http.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        claim.delete()
        return Response(status=http.HTTP_204_NO_CONTENT)

    serializer = ClaimUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        field, message = _first_error(serializer)
        return api_error("validation_error", message, http.HTTP_400_BAD_REQUEST, field)

    claim.text = serializer.validated_data["text"]
    claim.origin = Claim.Origin.USER
    claim.save(update_fields=["text", "origin", "updated_at"])
    return Response(ClaimSerializer(claim).data)


@api_view(["POST"])
def claims_approve(request: Request, thesis_id: str) -> Response:
    """Approve selected claims for analysis."""
    thesis = _thesis_queryset().filter(id=thesis_id).first()
    if thesis is None:
        return api_error("not_found", "No thesis with that id.", http.HTTP_404_NOT_FOUND)

    serializer = ClaimApproveSerializer(data=request.data)
    if not serializer.is_valid():
        field, message = _first_error(serializer)
        return api_error("validation_error", message, http.HTTP_400_BAD_REQUEST, field)

    requested = [str(claim_id) for claim_id in serializer.validated_data["claim_ids"]]
    owned = {str(pk) for pk in thesis.claims.values_list("id", flat=True)}
    unknown = [claim_id for claim_id in requested if claim_id not in owned]
    if unknown:
        return api_error(
            "validation_error",
            f"Claim ids not on this thesis: {', '.join(unknown)}.",
            http.HTTP_400_BAD_REQUEST,
            "claim_ids",
        )

    with transaction.atomic():
        thesis.claims.exclude(id__in=requested).update(is_approved=False)
        thesis.claims.filter(id__in=requested).update(is_approved=True)
        thesis.status = Thesis.Status.APPROVED
        thesis.save(update_fields=["status", "updated_at"])

    return Response(
        {"thesis_id": str(thesis.id), "status": thesis.status, "approved_claim_ids": requested}
    )


@api_view(["POST"])
def thesis_analyze(request: Request, thesis_id: str) -> Response:
    """Start analysis job for a thesis.

    Creates an AnalysisJob, checks cache for duplicate request, and
    enqueues the Celery task (or runs synchronously in dev).
    """
    thesis = Thesis.objects.select_related("company").filter(id=thesis_id).first()
    if thesis is None:
        return api_error("not_found", "No thesis with that id.", http.HTTP_404_NOT_FOUND)

    approved = thesis.claims.filter(is_approved=True).count()
    if approved == 0:
        return api_error(
            "validation_error",
            "Approve at least one claim before running an analysis.",
            http.HTTP_400_BAD_REQUEST,
            "claim_ids",
        )

    # Check for recent completed job with same cache_key (cache-aside)
    cache_key = compute_cache_key(thesis)
    existing_job = AnalysisJob.objects.filter(
        cache_key=cache_key,
        status__in=[AnalysisJob.Status.DONE, AnalysisJob.Status.PENDING, AnalysisJob.Status.RUNNING],
    ).first()

    if existing_job:
        return Response(
            {
                "job_id": str(existing_job.id),
                "status": existing_job.status,
                "thesis_id": str(thesis.id),
                "total_claims": existing_job.total_claims,
                "cached": True,
            },
            status=http.HTTP_202_ACCEPTED,
        )

    # Create new job
    job = create_analysis_job(thesis)

    # Import here to avoid circular import; task will be created in A5
    try:
        from apps.ledger.tasks import run_analysis_task
        run_analysis_task.delay(str(job.id))
    except ImportError:
        # Celery not set up yet; run synchronously for dev
        from apps.ledger.services import run_mock_analysis
        run_mock_analysis(job)

    return Response(
        {
            "job_id": str(job.id),
            "status": job.status,
            "thesis_id": str(thesis.id),
            "total_claims": job.total_claims,
        },
        status=http.HTTP_202_ACCEPTED,
    )


@api_view(["GET"])
def job_detail(request: Request, job_id: str) -> Response:
    """Get job status and results."""
    job = (
        AnalysisJob.objects
        .select_related("thesis__company")
        .prefetch_related("evidence__claim", "evidence__chunk__filing")
        .filter(id=job_id)
        .first()
    )
    if job is None:
        return api_error("not_found", "No job with that id.", http.HTTP_404_NOT_FOUND)

    results = []
    for evidence in job.evidence.all():
        source = None
        if evidence.chunk:
            filing = evidence.chunk.filing
            source = {
                "chunk_id": str(evidence.chunk.id),
                "section": evidence.chunk.section,
                "filing_type": filing.filing_type,
                "period_end": filing.period_end.isoformat(),
                "filed_at": filing.filed_at.isoformat(),
                "source_url": filing.source_url,
            }

        results.append({
            "claim": {
                "id": str(evidence.claim.id),
                "ordinal": evidence.claim.ordinal,
                "text": evidence.claim.text,
            },
            "evidence": {
                "id": str(evidence.id),
                "status": evidence.status,
                "explanation": evidence.explanation,
                "quote": evidence.quote,
                "similarity": evidence.similarity,
                "source": source,
            },
        })

    return Response({
        "id": str(job.id),
        "thesis_id": str(job.thesis_id),
        "status": job.status,
        "progress": job.progress,
        "total_claims": job.total_claims,
        "error": job.error or None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "results": results,
    })
