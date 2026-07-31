"""Shared pytest fixtures.

The suite must be hermetic. `thesis_create` calls `generate_claims`, which now
routes through `apps.rag.extraction` to a real Ollama endpoint — so with Ollama
running locally the tests would issue live LLM calls and take minutes each.
Stub it by default; a test that genuinely wants the model can override.
"""

import pytest

STUB_CLAIMS = [
    "Services revenue grows faster than product revenue.",
    "Gross margin expands as the services mix increases.",
    "The installed base of active devices keeps growing.",
]


@pytest.fixture(autouse=True)
def stub_claim_extraction(monkeypatch, request):
    """Replace the LLM claim extractor with a deterministic stub."""
    if "live_llm" in request.keywords:
        return

    monkeypatch.setattr(
        "apps.ledger.claim_generation.generate_claims_llm",
        lambda thesis_text, ticker: list(STUB_CLAIMS),
    )
