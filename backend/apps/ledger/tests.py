"""Contract tests: every stub response must match docs/api_contract.md.

These are the guard rail for Days 3–4 — when the stubs are swapped for real
persistence, the shapes asserted here must keep holding.
"""

import pytest
from django.urls import reverse

from apps.ledger.models import Company
from apps.ledger.stubs import STUB_CLAIM_IDS, STUB_JOB_ID, STUB_THESIS_ID

CLAIM_FIELDS = {"id", "ordinal", "text", "origin", "is_approved"}
THESIS_FIELDS = {"id", "company", "text", "status", "claims", "created_at"}
EVIDENCE_FIELDS = {"id", "status", "explanation", "quote", "similarity", "source"}
SOURCE_FIELDS = {"chunk_id", "section", "filing_type", "period_end", "filed_at", "source_url"}
JOB_FIELDS = {
    "id",
    "thesis_id",
    "status",
    "progress",
    "total_claims",
    "error",
    "started_at",
    "finished_at",
    "results",
}


@pytest.fixture
def company(db) -> Company:
    return Company.objects.create(ticker="AAPL", name="Apple Inc.", cik="0000320193")


@pytest.mark.django_db
def test_company_list_returns_seeded_companies(client, company):
    response = client.get(reverse("company-list"))

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert set(results[0]) == {"id", "ticker", "name", "cik", "filing_count"}
    assert results[0]["ticker"] == "AAPL"
    assert results[0]["filing_count"] == 0


@pytest.mark.django_db
def test_company_list_hides_inactive(client, company):
    company.is_active = False
    company.save(update_fields=["is_active"])

    assert client.get(reverse("company-list")).json()["results"] == []


@pytest.mark.django_db
def test_create_thesis_returns_contract_shape(client, company):
    response = client.post(
        reverse("thesis-create"),
        {"company_id": str(company.id), "text": "Services outgrow hardware."},
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == THESIS_FIELDS
    assert body["status"] == "draft"
    assert body["claims"] == []
    assert body["text"] == "Services outgrow hardware."
    assert set(body["company"]) == {"id", "ticker", "name"}


@pytest.mark.django_db
def test_create_thesis_rejects_blank_text(client, company):
    response = client.post(
        reverse("thesis-create"),
        {"company_id": str(company.id), "text": "  "},
        content_type="application/json",
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["field"] == "text"


@pytest.mark.django_db
def test_create_thesis_unknown_company_is_404(client, company):
    response = client.post(
        reverse("thesis-create"),
        {"company_id": "99999999-9999-4999-8999-999999999999", "text": "Anything."},
        content_type="application/json",
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_thesis_detail_shape(client, company):
    response = client.get(reverse("thesis-detail", args=[STUB_THESIS_ID]))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == THESIS_FIELDS
    assert body["id"] == STUB_THESIS_ID
    assert all(set(claim) == CLAIM_FIELDS for claim in body["claims"])


@pytest.mark.django_db
def test_generate_claims_returns_at_most_five(client):
    response = client.post(reverse("claims-generate", args=[STUB_THESIS_ID]))

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"thesis_id", "status", "claims"}
    assert body["status"] == "claims_generated"
    assert 0 < len(body["claims"]) <= 5
    assert all(set(claim) == CLAIM_FIELDS for claim in body["claims"])


@pytest.mark.django_db
def test_patch_claim_marks_origin_user(client):
    response = client.patch(
        reverse("claim-detail", args=[STUB_CLAIM_IDS[0]]),
        {"text": "Edited claim."},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == CLAIM_FIELDS
    assert body["text"] == "Edited claim."
    assert body["origin"] == "user"


@pytest.mark.django_db
def test_delete_claim_returns_204(client):
    response = client.delete(reverse("claim-detail", args=[STUB_CLAIM_IDS[0]]))

    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.django_db
def test_approve_claims_shape(client):
    response = client.post(
        reverse("claims-approve", args=[STUB_THESIS_ID]),
        {"claim_ids": STUB_CLAIM_IDS[:2]},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"thesis_id", "status", "approved_claim_ids"}
    assert body["approved_claim_ids"] == STUB_CLAIM_IDS[:2]


@pytest.mark.django_db
def test_approve_rejects_empty_list(client):
    response = client.post(
        reverse("claims-approve", args=[STUB_THESIS_ID]),
        {"claim_ids": []},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["field"] == "claim_ids"


@pytest.mark.django_db
def test_analyze_returns_job_id(client):
    response = client.post(reverse("thesis-analyze", args=[STUB_THESIS_ID]))

    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"job_id", "status", "thesis_id", "total_claims"}
    assert body["status"] == "pending"


@pytest.mark.django_db
def test_job_detail_shape_and_citation_rule(client):
    response = client.get(reverse("job-detail", args=[STUB_JOB_ID]))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == JOB_FIELDS
    assert body["progress"] == body["total_claims"] == len(body["results"])

    for result in body["results"]:
        assert set(result) == {"claim", "evidence"}
        evidence = result["evidence"]
        assert set(evidence) == EVIDENCE_FIELDS
        assert evidence["status"] in {"supported", "contradicted", "insufficient_evidence"}
        if evidence["status"] == "insufficient_evidence":
            assert evidence["source"] is None
        else:
            # Contract rule: any non-insufficient verdict carries a real citation.
            assert set(evidence["source"]) == SOURCE_FIELDS
            assert evidence["quote"]
