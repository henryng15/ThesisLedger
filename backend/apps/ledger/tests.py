"""Contract + persistence tests for the ledger API (docs/api_contract.md).

Every endpoint is backed by the database; the job tests build real AnalysisJob
and Evidence rows rather than the Day 2 fixtures they used to assert against.
"""

from datetime import date
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.ledger.models import (
    AnalysisJob,
    Chunk,
    Claim,
    Company,
    Evidence,
    Filing,
    Thesis,
)

QUOTE = "Services revenue reached an all-time high for the fiscal year."
CHUNK_TEXT = f"Management discussion follows. {QUOTE} Growth was broad based."

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

UNKNOWN_UUID = "99999999-9999-4999-8999-999999999999"


@pytest.fixture
def company(db) -> Company:
    return Company.objects.create(ticker="AAPL", name="Apple Inc.", cik="0000320193")


@pytest.fixture
def thesis(company) -> Thesis:
    return Thesis.objects.create(company=company, text="Services outgrow hardware.")


@pytest.fixture
def claims(thesis) -> list[Claim]:
    return [
        Claim.objects.create(thesis=thesis, ordinal=ordinal, text=f"Claim {ordinal}.")
        for ordinal in range(3)
    ]


@pytest.fixture
def finished_job(thesis, claims) -> AnalysisJob:
    """A completed job with one cited verdict and one insufficient-evidence row."""
    filing = Filing.objects.create(
        company=thesis.company,
        filing_type=Filing.FilingType.ANNUAL,
        period_end=date(2024, 9, 30),
        filed_at=date(2024, 10, 30),
        accession_number="0000320193-24-000123",
        source_url="https://example.com/aapl-10k",
        raw_text=CHUNK_TEXT,
    )
    chunk = Chunk.objects.create(
        filing=filing, ordinal=0, section="Item 7", text=CHUNK_TEXT, char_end=len(CHUNK_TEXT)
    )

    job = AnalysisJob.objects.create(
        thesis=thesis,
        status=AnalysisJob.Status.DONE,
        progress=2,
        total_claims=2,
        started_at=timezone.now(),
        finished_at=timezone.now(),
    )
    Evidence.objects.create(
        job=job,
        claim=claims[0],
        status=Evidence.Status.SUPPORTED,
        explanation="Services revenue grew year over year.",
        quote=QUOTE,
        chunk=chunk,
        similarity=0.91,
    )
    Evidence.objects.create(
        job=job,
        claim=claims[1],
        status=Evidence.Status.INSUFFICIENT,
        explanation="No passage addressed this claim.",
    )
    return job


def post_json(client, url, payload=None):
    return client.post(url, payload or {}, content_type="application/json")


# --- companies -------------------------------------------------------------


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


# --- thesis create / read --------------------------------------------------


@pytest.mark.django_db
def test_create_thesis_persists_row(client, company):
    response = post_json(
        client,
        reverse("thesis-create"),
        {"company_id": str(company.id), "text": "Services outgrow hardware."},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == THESIS_FIELDS
    assert body["status"] == "draft"
    assert body["claims"] == []
    assert set(body["company"]) == {"id", "ticker", "name"}

    stored = Thesis.objects.get(id=body["id"])
    assert stored.text == "Services outgrow hardware."
    assert stored.company_id == company.id


@pytest.mark.django_db
def test_create_thesis_rejects_blank_text(client, company):
    response = post_json(
        client, reverse("thesis-create"), {"company_id": str(company.id), "text": "  "}
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["field"] == "text"
    assert Thesis.objects.count() == 0


@pytest.mark.django_db
def test_create_thesis_rejects_text_over_limit(client, company):
    response = post_json(
        client, reverse("thesis-create"), {"company_id": str(company.id), "text": "x" * 5001}
    )

    assert response.status_code == 400
    assert response.json()["error"]["field"] == "text"


@pytest.mark.django_db
def test_create_thesis_unknown_company_is_404(client, company):
    response = post_json(
        client, reverse("thesis-create"), {"company_id": UNKNOWN_UUID, "text": "Anything."}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_thesis_detail_returns_persisted_claims(client, thesis, claims):
    response = client.get(reverse("thesis-detail", args=[thesis.id]))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == THESIS_FIELDS
    assert body["id"] == str(thesis.id)
    assert [claim["text"] for claim in body["claims"]] == ["Claim 0.", "Claim 1.", "Claim 2."]
    assert all(set(claim) == CLAIM_FIELDS for claim in body["claims"])


@pytest.mark.django_db
def test_thesis_detail_unknown_id_is_404(client, company):
    response = client.get(reverse("thesis-detail", args=[UNKNOWN_UUID]))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- claim generation ------------------------------------------------------


@pytest.mark.django_db
def test_generate_claims_persists_at_most_five(client, thesis):
    response = post_json(client, reverse("claims-generate", args=[thesis.id]))

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"thesis_id", "status", "claims"}
    assert body["status"] == "claims_generated"
    assert 0 < len(body["claims"]) <= Claim.MAX_PER_THESIS
    assert all(set(claim) == CLAIM_FIELDS for claim in body["claims"])

    thesis.refresh_from_db()
    assert thesis.status == Thesis.Status.CLAIMS_GENERATED
    assert thesis.claims.count() == len(body["claims"])
    assert list(thesis.claims.values_list("ordinal", flat=True)) == list(range(len(body["claims"])))


@pytest.mark.django_db
def test_generate_claims_twice_conflicts(client, thesis):
    post_json(client, reverse("claims-generate", args=[thesis.id]))
    response = post_json(client, reverse("claims-generate", args=[thesis.id]))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.django_db
def test_generate_claims_force_replaces(client, thesis):
    first = post_json(client, reverse("claims-generate", args=[thesis.id])).json()
    second = post_json(client, reverse("claims-generate", args=[thesis.id]), {"force": True})

    assert second.status_code == 201
    new_ids = {claim["id"] for claim in second.json()["claims"]}
    old_ids = {claim["id"] for claim in first["claims"]}
    assert new_ids.isdisjoint(old_ids)
    assert thesis.claims.count() == len(new_ids)


@pytest.mark.django_db
def test_generate_claims_unknown_thesis_is_404(client, company):
    response = post_json(client, reverse("claims-generate", args=[UNKNOWN_UUID]))

    assert response.status_code == 404


# --- claim edit / delete ---------------------------------------------------


@pytest.mark.django_db
def test_patch_claim_persists_text_and_marks_origin_user(client, claims):
    claim = claims[0]
    response = client.patch(
        reverse("claim-detail", args=[claim.id]),
        {"text": "Edited claim."},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == CLAIM_FIELDS
    claim.refresh_from_db()
    assert claim.text == "Edited claim."
    assert claim.origin == Claim.Origin.USER


@pytest.mark.django_db
def test_patch_claim_rejects_blank_text(client, claims):
    response = client.patch(
        reverse("claim-detail", args=[claims[0].id]),
        {"text": "   "},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["field"] == "text"


@pytest.mark.django_db
def test_delete_claim_removes_row(client, claims):
    response = client.delete(reverse("claim-detail", args=[claims[0].id]))

    assert response.status_code == 204
    assert response.content == b""
    assert not Claim.objects.filter(id=claims[0].id).exists()


@pytest.mark.django_db
def test_patch_unknown_claim_is_404(client, company):
    response = client.patch(
        reverse("claim-detail", args=[UNKNOWN_UUID]),
        {"text": "Nope."},
        content_type="application/json",
    )

    assert response.status_code == 404


# --- approval --------------------------------------------------------------


@pytest.mark.django_db
def test_approve_marks_selected_claims_only(client, thesis, claims):
    approved_ids = [str(claims[0].id), str(claims[2].id)]
    response = post_json(
        client, reverse("claims-approve", args=[thesis.id]), {"claim_ids": approved_ids}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"thesis_id", "status", "approved_claim_ids"}
    assert body["status"] == "approved"
    assert body["approved_claim_ids"] == approved_ids

    thesis.refresh_from_db()
    assert thesis.status == Thesis.Status.APPROVED
    assert set(thesis.claims.filter(is_approved=True).values_list("id", flat=True)) == {
        claims[0].id,
        claims[2].id,
    }


@pytest.mark.django_db
def test_approve_rejects_claim_from_another_thesis(client, thesis, claims, company):
    other = Thesis.objects.create(company=company, text="Other thesis.")
    foreign = Claim.objects.create(thesis=other, ordinal=0, text="Foreign claim.")

    response = post_json(
        client, reverse("claims-approve", args=[thesis.id]), {"claim_ids": [str(foreign.id)]}
    )

    assert response.status_code == 400
    assert response.json()["error"]["field"] == "claim_ids"
    foreign.refresh_from_db()
    assert foreign.is_approved is False


@pytest.mark.django_db
def test_approve_rejects_empty_list(client, thesis, claims):
    response = post_json(client, reverse("claims-approve", args=[thesis.id]), {"claim_ids": []})

    assert response.status_code == 400
    assert response.json()["error"]["field"] == "claim_ids"


# --- upload flow ----------------------------------------------------------


@pytest.mark.django_db
def test_upload_file_persists_to_media_storage(client, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "uploads"
    settings.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

    payload = SimpleUploadedFile("sample.txt", b"hello world", content_type="text/plain")
    response = client.post(reverse("upload-file"), {"file": payload}, format="multipart")

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "sample.txt"
    assert body["size"] == 11
    assert Path(body["path"]).exists()


# --- analyze / job (stubbed until Day 4) -----------------------------------


@pytest.mark.django_db
def test_analyze_requires_an_approved_claim(client, thesis, claims):
    response = post_json(client, reverse("thesis-analyze", args=[thesis.id]))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_analyze_returns_job_id(client, thesis, claims):
    claims[0].is_approved = True
    claims[0].save(update_fields=["is_approved"])

    response = post_json(client, reverse("thesis-analyze", args=[thesis.id]))

    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"job_id", "status", "thesis_id", "total_claims"}
    # Normally "pending" (queued for a worker). When the broker is unreachable
    # the analysis runs inline, so the job can already be terminal here.
    assert body["status"] in {"pending", "running", "done"}
    assert body["total_claims"] == 1


@pytest.mark.django_db
def test_job_detail_shape_and_citation_rule(client, finished_job):
    response = client.get(reverse("job-detail", args=[finished_job.id]))

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
