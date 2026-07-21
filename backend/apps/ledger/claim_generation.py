"""Claim extraction seam.

Day 3 returns a fixed list so the UI has real rows to edit and approve. Day 7
swaps the body of `generate_claims` for the LangGraph extraction node — the
signature and the `MAX_CLAIMS` cap stay as they are.
"""

from apps.ledger.models import Claim, Thesis

MAX_CLAIMS = Claim.MAX_PER_THESIS

MOCK_CLAIM_TEXTS = [
    "Services revenue grows faster than product revenue.",
    "Gross margin expands as the services mix increases.",
    "The installed base of active devices keeps growing.",
]


def generate_claims(thesis: Thesis) -> list[str]:
    """Return at most MAX_CLAIMS testable statements extracted from the thesis."""
    return MOCK_CLAIM_TEXTS[:MAX_CLAIMS]
