"""Tests for the citation-integrity rule.

A verdict other than insufficient_evidence must carry a quote found verbatim in
a retrieved chunk. This is the product's core guarantee, so it gets a test that
fails loudly rather than a comment.
"""

from types import SimpleNamespace

import pytest

from apps.rag import classification


class FakeChunk(SimpleNamespace):
    pass


CHUNK = FakeChunk(id="11111111-1111-4111-8111-111111111111", text="Services revenue grew 14% this year.", section="Item 7")


class FakeChain:
    """Stands in for `prompt | llm`, which the view builds with the | operator."""

    def __init__(self, content: str):
        self.content = content

    def __or__(self, _other):
        return self

    def invoke(self, _vars):
        return SimpleNamespace(content=self.content)


def _patch(monkeypatch, llm_json: str):
    monkeypatch.setattr(classification, "search_chunks_real", lambda *a, **kw: [CHUNK])
    monkeypatch.setattr(classification, "CLASSIFICATION_PROMPT", FakeChain(llm_json))
    monkeypatch.setattr(classification, "get_llm", lambda *a, **kw: object())


def test_verbatim_quote_is_kept_and_cited(monkeypatch):
    _patch(monkeypatch, '{"status":"supported","explanation":"ok","quote":"Services revenue grew 14%"}')

    result = classification.classify_claim("Services grew.", "cid", "AAPL")

    assert result.status == "supported"
    assert result.chunk_id == CHUNK.id


def test_supported_without_a_quote_is_downgraded(monkeypatch):
    """The model asserting support with no citation must not stand."""
    _patch(monkeypatch, '{"status":"supported","explanation":"looks right","quote":""}')

    result = classification.classify_claim("Services grew.", "cid", "AAPL")

    assert result.status == "insufficient_evidence"
    assert result.quote == ""
    assert result.chunk_id is None


def test_quote_absent_from_sources_is_downgraded(monkeypatch):
    """A fabricated quote must not become a citation."""
    _patch(monkeypatch, '{"status":"contradicted","explanation":"x","quote":"Revenue fell sharply"}')

    result = classification.classify_claim("Services grew.", "cid", "AAPL")

    assert result.status == "insufficient_evidence"
    assert result.chunk_id is None


@pytest.mark.parametrize("payload", ['not json at all', '{"status":"maybe"}', '[]'])
def test_unparseable_or_unknown_status_falls_back_safely(monkeypatch, payload):
    _patch(monkeypatch, payload)

    result = classification.classify_claim("Services grew.", "cid", "AAPL")

    assert result.status == "insufficient_evidence"
