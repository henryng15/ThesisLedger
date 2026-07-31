import pytest

from apps.ledger.claim_generation import FALLBACK_CLAIM_TEXTS, generate_claims
from apps.ledger.embeddings import EmbeddingService, EmbeddingServiceError
from apps.ledger.llm_service import LLMService, LLMServiceError
from apps.ledger.models import Thesis


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("bad request")

    def json(self):
        return self._payload


def test_generate_claims_falls_back_when_llm_unavailable(monkeypatch):
    class BrokenService(LLMService):
        def generate_claims(self, thesis_text, max_claims=3):
            raise LLMServiceError("down")

    monkeypatch.setattr("apps.ledger.claim_generation.build_llm_service", lambda: BrokenService())
    thesis = Thesis(text="Services outgrow hardware")
    claims = generate_claims(thesis)
    assert claims == FALLBACK_CLAIM_TEXTS[:3]


def test_embedding_service_parses_payload(monkeypatch):
    payload = {"embedding": [0.1, 0.2, 0.3]}

    class DummyRequests:
        @staticmethod
        def post(*args, **kwargs):
            return DummyResponse(payload)

    monkeypatch.setattr("apps.ledger.embeddings.requests", DummyRequests)
    service = EmbeddingService(base_url="http://localhost:11434", model="nomic-embed-text")
    assert service.embed_text("hello") == [0.1, 0.2, 0.3]


def test_embedding_service_raises_clear_error(monkeypatch):
    class DummyRequests:
        @staticmethod
        def post(*args, **kwargs):
            return DummyResponse({"unexpected": True})

    monkeypatch.setattr("apps.ledger.embeddings.requests", DummyRequests)
    service = EmbeddingService(base_url="http://localhost:11434", model="nomic-embed-text")
    with pytest.raises(EmbeddingServiceError):
        service.embed_text("hello")
