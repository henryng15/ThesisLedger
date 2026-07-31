"""Shared pytest fixtures.

The suite must be hermetic. `thesis_create` calls `generate_claims`, which now
routes through `apps.rag.extraction` to a real Ollama endpoint — so with Ollama
running locally the tests would issue live LLM calls and take minutes each.
Stub it by default; a test that genuinely wants the model can override.
"""

import pytest

from config.celery import app as celery_app

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


@pytest.fixture(autouse=True)
def eager_celery():
    """Run tasks in-process.

    Otherwise whether a task executes depends on a Redis broker being up, which
    makes the same test pass or fail depending on the developer's machine.
    """
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
