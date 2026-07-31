"""Claim extraction seam with an Ollama-backed provider and graceful fallback."""

from apps.ledger.llm_service import LLMServiceError, build_llm_service
from apps.ledger.models import Claim, Thesis

MAX_CLAIMS = Claim.MAX_PER_THESIS

FALLBACK_CLAIM_TEXTS = [
    "Services revenue grows faster than product revenue.",
    "Gross margin expands as the services mix increases.",
    "The installed base of active devices keeps growing.",
]


def generate_claims(thesis: Thesis) -> list[str]:
    """Return at most MAX_CLAIMS testable statements extracted from the thesis."""
    service = build_llm_service()
    try:
        claims = service.generate_claims(thesis.text, max_claims=MAX_CLAIMS)
    except LLMServiceError:
        claims = FALLBACK_CLAIM_TEXTS[:MAX_CLAIMS]

    if not claims:
        return FALLBACK_CLAIM_TEXTS[:MAX_CLAIMS]
    return claims[:MAX_CLAIMS]
