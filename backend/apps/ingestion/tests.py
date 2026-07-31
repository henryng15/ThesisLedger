"""Tests for the ingestion pipeline.

Ports the coverage that used to live in apps/ledger/tests_day5.py and
tests_day67.py, which tested the parallel implementation removed during the
branch merge.
"""

from datetime import date

import pytest

from apps.ingestion import embeddings as embeddings_module
from apps.ingestion.chunker import chunk_text
from apps.ingestion.cleaner import clean_filing_html, detect_filing_type
from apps.ingestion.pipeline import IngestionError, ingest_filing
from apps.ledger.models import Company, Filing

FILING_TEXT = "Alpha paragraph about revenue.\n\nBeta paragraph about margin.\n\nGamma paragraph."


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("bad request")

    def json(self):
        return self._payload


@pytest.fixture
def company(db):
    return Company.objects.create(ticker="AAPL", name="Apple Inc.", cik="0000320193")


def test_chunk_text_is_deterministic():
    first = [c.text for c in chunk_text(FILING_TEXT)]
    second = [c.text for c in chunk_text(FILING_TEXT)]
    assert first == second
    assert all(first)


def test_chunk_text_yields_single_chunk_below_minimum_size():
    chunks = list(chunk_text("Short filing text."))
    assert len(chunks) == 1
    assert chunks[0].ordinal == 0


def test_clean_filing_html_strips_markup():
    cleaned = clean_filing_html("<html><body><p>Revenue grew</p><script>x=1</script></body></html>")
    assert "Revenue grew" in cleaned
    assert "<p>" not in cleaned
    assert "x=1" not in cleaned


def test_detect_filing_type_recognises_annual_report():
    assert detect_filing_type("ANNUAL REPORT PURSUANT TO SECTION 13 FORM 10-K") == "10-K"


def test_ingest_filing_creates_filing_and_chunks(company):
    filing = ingest_filing(
        company,
        filing_type=Filing.FilingType.ANNUAL,
        period_end=date(2024, 9, 30),
        filed_at=date(2024, 10, 30),
        accession_number="0001",
        source_url="https://example.com/10k",
        raw_text=FILING_TEXT,
    )

    assert filing.raw_text == FILING_TEXT
    assert filing.chunks.count() >= 1
    assert filing.ingested_at is not None


def test_ingest_filing_rejects_text_with_no_chunks(company):
    with pytest.raises(IngestionError):
        ingest_filing(
            company,
            filing_type=Filing.FilingType.ANNUAL,
            period_end=date(2024, 9, 30),
            filed_at=date(2024, 10, 30),
            accession_number="0002",
            source_url="https://example.com/10k-2",
            raw_text="   ",
        )

    assert Filing.objects.filter(accession_number="0002").count() == 0


def test_get_embedding_parses_payload(monkeypatch):
    monkeypatch.setattr(
        embeddings_module.httpx, "post", lambda *a, **kw: DummyResponse({"embedding": [0.1, 0.2, 0.3]})
    )
    assert embeddings_module.get_embedding("hello") == [0.1, 0.2, 0.3]


def test_get_embedding_raises_on_unexpected_payload(monkeypatch):
    monkeypatch.setattr(
        embeddings_module.httpx, "post", lambda *a, **kw: DummyResponse({"unexpected": True})
    )
    with pytest.raises(ValueError):
        embeddings_module.get_embedding("hello")
