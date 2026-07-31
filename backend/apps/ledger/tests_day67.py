from datetime import date

import pytest

from apps.ledger.evidence import build_evidence_for_claim
from apps.ledger.graph import build_graph_state, run_graph
from apps.ledger.ingestion import chunk_text, ingest_filing
from apps.ledger.models import AnalysisJob, Claim, Company, Evidence, Filing, Thesis


@pytest.fixture
def company(db):
    return Company.objects.create(ticker="AAPL", name="Apple Inc.", cik="0000320193")


@pytest.fixture
def thesis(company):
    return Thesis.objects.create(company=company, text="Services outgrow hardware")


@pytest.fixture
def claim(thesis):
    return Claim.objects.create(thesis=thesis, ordinal=0, text="Services are growing")


def test_chunk_text_split_is_deterministic():
    text = "alpha\n\nbeta\n\ngamma"
    chunks = chunk_text(text, chunk_size=20)
    assert len(chunks) >= 2
    assert all(chunks)


def test_ingest_filing_creates_filing_and_chunks(company):
    filing = ingest_filing(
        company,
        filing_type=Filing.FilingType.ANNUAL,
        period_end=date(2024, 9, 30),
        filed_at=date(2024, 10, 30),
        accession_number="0001",
        source_url="https://example.com/10k",
        raw_text="Alpha paragraph\n\nBeta paragraph",
    )

    assert filing.chunks.count() >= 1
    assert filing.raw_text == "Alpha paragraph\n\nBeta paragraph"


def test_build_evidence_for_claim_creates_supported_row(thesis, claim):
    company = thesis.company
    filing = ingest_filing(
        company,
        filing_type=Filing.FilingType.ANNUAL,
        period_end=date(2024, 9, 30),
        filed_at=date(2024, 10, 30),
        accession_number="0002",
        source_url="https://example.com/10k-2",
        raw_text="Alpha paragraph\n\nBeta paragraph",
    )
    job = AnalysisJob.objects.create(thesis=thesis)

    evidence = build_evidence_for_claim(claim, job)

    assert evidence.status == Evidence.Status.SUPPORTED
    assert evidence.chunk is not None


def test_run_graph_persists_graph_state(thesis, claim):
    company = thesis.company
    ingest_filing(
        company,
        filing_type=Filing.FilingType.ANNUAL,
        period_end=date(2024, 9, 30),
        filed_at=date(2024, 10, 30),
        accession_number="0003",
        source_url="https://example.com/10k-3",
        raw_text="Alpha paragraph\n\nBeta paragraph",
    )
    claim.is_approved = True
    claim.save(update_fields=["is_approved"])
    job = AnalysisJob.objects.create(thesis=thesis)

    graph_state = run_graph(job)

    assert graph_state["claims"] == [claim.text]
    assert job.graph_state["claims"] == [claim.text]
