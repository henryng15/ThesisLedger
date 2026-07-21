"""Day 2 stub API. Shapes match docs/api_contract.md; only `companies` reads the DB.

Each view is replaced by real persistence on Days 3–4. Keep the response shapes
identical when swapping — the frontend and apps/ledger/tests.py depend on them.
"""

from django.db.models import Count
from rest_framework import status as http
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.ledger import stubs
from apps.ledger.models import Company
from apps.ledger.serializers import (
    ClaimApproveSerializer,
    ClaimUpdateSerializer,
    CompanySerializer,
    ThesisCreateSerializer,
)


def api_error(code: str, message: str, status_code: int, field: str | None = None) -> Response:
    """The single error envelope defined in the contract."""
    return Response(
        {"error": {"code": code, "message": message, "field": field}}, status=status_code
    )


def _first_error(serializer: ThesisCreateSerializer) -> tuple[str, str]:
    field, messages = next(iter(serializer.errors.items()))
    return field, str(messages[0])


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

    payload = _stub_thesis(company, text=serializer.validated_data["text"], claims=[])
    return Response(payload, status=http.HTTP_201_CREATED)


@api_view(["GET"])
def thesis_detail(request: Request, thesis_id: str) -> Response:
    company = Company.objects.filter(is_active=True).order_by("ticker").first()
    if company is None:
        return api_error(
            "not_found", "No companies seeded; run manage.py seed_companies.", http.HTTP_404_NOT_FOUND
        )

    payload = _stub_thesis(company, text=stubs.STUB_THESIS_TEXT, claims=stubs.STUB_CLAIMS)
    payload["id"] = str(thesis_id)
    payload["status"] = "claims_generated"
    return Response(payload)


@api_view(["POST"])
def claims_generate(request: Request, thesis_id: str) -> Response:
    return Response(
        {
            "thesis_id": str(thesis_id),
            "status": "claims_generated",
            "claims": stubs.STUB_CLAIMS,
        },
        status=http.HTTP_201_CREATED,
    )


@api_view(["PATCH", "DELETE"])
def claim_detail(request: Request, claim_id: str) -> Response:
    if request.method == "DELETE":
        return Response(status=http.HTTP_204_NO_CONTENT)

    serializer = ClaimUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        field, message = _first_error(serializer)
        return api_error("validation_error", message, http.HTTP_400_BAD_REQUEST, field)

    claim = dict(stubs.STUB_CLAIMS[0])
    claim["id"] = str(claim_id)
    claim["text"] = serializer.validated_data["text"]
    claim["origin"] = "user"
    return Response(claim)


@api_view(["POST"])
def claims_approve(request: Request, thesis_id: str) -> Response:
    serializer = ClaimApproveSerializer(data=request.data)
    if not serializer.is_valid():
        field, message = _first_error(serializer)
        return api_error("validation_error", message, http.HTTP_400_BAD_REQUEST, field)

    approved = [str(claim_id) for claim_id in serializer.validated_data["claim_ids"]]
    return Response({"thesis_id": str(thesis_id), "status": "approved", "approved_claim_ids": approved})


@api_view(["POST"])
def thesis_analyze(request: Request, thesis_id: str) -> Response:
    return Response(
        {
            "job_id": stubs.STUB_JOB_ID,
            "status": "pending",
            "thesis_id": str(thesis_id),
            "total_claims": len(stubs.STUB_CLAIMS),
        },
        status=http.HTTP_202_ACCEPTED,
    )


@api_view(["GET"])
def job_detail(request: Request, job_id: str) -> Response:
    payload = dict(stubs.STUB_JOB)
    payload["id"] = str(job_id)
    return Response(payload)


def _stub_thesis(company: Company, text: str, claims: list[dict]) -> dict:
    return {
        "id": stubs.STUB_THESIS_ID,
        "company": {"id": str(company.id), "ticker": company.ticker, "name": company.name},
        "text": text,
        "status": "draft",
        "claims": claims,
        "created_at": "2026-07-21T20:00:00Z",
    }
