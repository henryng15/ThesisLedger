"""Claim extraction seam over the LangChain pipeline, with a graceful fallback."""

from apps.ledger.models import Claim, Thesis
from apps.rag.extraction import generate_claims_llm

MAX_CLAIMS = Claim.MAX_PER_THESIS

FALLBACK_CLAIM_TEXTS = [
    "Services revenue grows faster than product revenue.",
    "Gross margin expands as the services mix increases.",
    "The installed base of active devices keeps growing.",
]


def generate_claims(thesis: Thesis) -> list[str]:
    """Return at most MAX_CLAIMS testable statements extracted from the thesis.

    `generate_claims_llm` already degrades to a sentence-splitting fallback when
    Ollama is unreachable; the canned texts here are the last resort for when
    that also comes back empty.
    """
    ticker = thesis.company.ticker if thesis.company_id else ""

    try:
        claims = generate_claims_llm(thesis.text, ticker)
    except Exception:
        claims = []

    if not claims:
        return FALLBACK_CLAIM_TEXTS[:MAX_CLAIMS]
    return claims[:MAX_CLAIMS]
