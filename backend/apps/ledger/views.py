"""REST API. Shapes come from docs/api_contract.md.

Thesis and claim endpoints hit the database (Day 3). `analyze` and `jobs` still
return the Day 2 fixtures until the AnalysisJob lifecycle lands on Day 4.
"""

from django.db import transaction
from django.db.models import Count
from rest_framework import status as http
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.ledger import stubs
from apps.ledger.claim_generation import generate_claims
from apps.ledger.graph import run_graph
from apps.ledger.models import AnalysisJob, Claim, Company, Thesis
from apps.ledger.uploads.handlers import save_uploaded_file
from apps.ledger.serializers import (
    ClaimApproveSerializer,
    ClaimSerializer,
    ClaimUpdateSerializer,
    CompanySerializer,
    ThesisCreateSerializer,
    ThesisSerializer,
)


def api_error(code: str, message: str, status_code: int, field: str | None = None) -> Response:
    """The single error envelope defined in the contract."""
    return Response(
        {"error": {"code": code, "message": message, "field": field}}, status=status_code
    )


def _first_error(serializer) -> tuple[str, str]:
    field, messages = next(iter(serializer.errors.items()))
    return field, str(messages[0])


def _thesis_queryset():
    return Thesis.objects.select_related("company").prefetch_related("claims")


@api_view(["POST"])
def upload_file(request: Request) -> Response:
    uploaded_file = request.FILES.get("file")
    if uploaded_file is None:
        return api_error("validation_error", "A file is required.", http.HTTP_400_BAD_REQUEST, "file")

    metadata = save_uploaded_file(uploaded_file)
    return Response(metadata, status=http.HTTP_201_CREATED)


@api_view(["GET"])
def company_list(request: Request) -> Response:
    companies = (
        Company.objects.filter(is_active=True)
        .annotate(filing_count=Count("filings"))
        .order_by("ticker")
    )
    return Response({"results": CompanySerializer(companies, many=True).data})


@api_view(["POST"])
def thesis_create(request: Request) -> Response:
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
    thesis = _thesis_queryset().filter(id=thesis_id).first()
    if thesis is None:
        return api_error("not_found", "No thesis with that id.", http.HTTP_404_NOT_FOUND)

    return Response(ThesisSerializer(thesis).data)


@api_view(["POST"])
def claims_generate(request: Request, thesis_id: str) -> Response:
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
    """Create a persisted analysis job and run the graph flow for approved claims."""
    thesis = Thesis.objects.filter(id=thesis_id).first()
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

    with transaction.atomic():
        job = AnalysisJob.objects.create(thesis=thesis, status=AnalysisJob.Status.PENDING, total_claims=approved)
        job.status = AnalysisJob.Status.RUNNING
        job.save(update_fields=["status", "updated_at"])
        graph_state = run_graph(job)

    return Response(
        {
            "job_id": str(job.id),
            "status": job.status,
            "thesis_id": str(thesis.id),
            "total_claims": approved,
        },
        status=http.HTTP_202_ACCEPTED,
    )


@api_view(["GET"])
def job_detail(request: Request, job_id: str) -> Response:
    """Return the persisted analysis job and its evidence rows when available."""
    job = AnalysisJob.objects.filter(id=job_id).select_related("thesis").prefetch_related("evidence").first()
    if job is None:
        return api_error("not_found", "No job with that id.", http.HTTP_404_NOT_FOUND)

    results = []
    for evidence in job.evidence.select_related("claim").all():
        results.append(
            {
                "claim": {"id": str(evidence.claim_id), "text": evidence.claim.text},
                "evidence": {
                    "id": str(evidence.id),
                    "status": evidence.status,
                    "explanation": evidence.explanation,
                    "quote": evidence.quote,
                    "similarity": evidence.similarity,
                    "source": None
                    if evidence.chunk is None
                    else {
                        "chunk_id": str(evidence.chunk_id),
                        "section": evidence.chunk.section,
                        "filing_type": evidence.chunk.filing.filing_type,
                        "period_end": evidence.chunk.filing.period_end,
                        "filed_at": evidence.chunk.filing.filed_at,
                        "source_url": evidence.chunk.filing.source_url,
                    },
                },
            }
        )

    return Response(
        {
            "id": str(job.id),
            "thesis_id": str(job.thesis_id),
            "status": job.status,
            "progress": job.progress,
            "total_claims": job.total_claims,
            "error": job.error,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "results": results,
        }
    )
