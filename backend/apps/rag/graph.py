"""LangGraph pipeline for full thesis analysis.

Orchestrates the flow: extract claims → classify each claim → collect results.
Designed to be resumable and support progress tracking.
"""

import logging
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph

from apps.rag.classification import classify_claim
from apps.rag.extraction import generate_claims_llm

logger = logging.getLogger(__name__)


class ClaimResult(TypedDict):
    """Result for a single claim."""

    claim_text: str
    claim_ordinal: int
    status: str
    explanation: str
    quote: str
    chunk_id: str | None
    similarity: float | None


class AnalysisState(TypedDict):
    """State passed through the analysis graph."""

    thesis_id: str
    thesis_text: str
    company_id: str
    company_ticker: str
    claims: list[str]
    current_claim_idx: int
    results: Annotated[list[ClaimResult], lambda a, b: a + b]
    error: str | None


def extract_claims_node(state: AnalysisState) -> dict:
    """Extract claims from thesis using LLM."""
    logger.info(f"Extracting claims for thesis {state['thesis_id']}")

    try:
        claims = generate_claims_llm(
            state["thesis_text"],
            state["company_ticker"],
        )
        return {"claims": claims, "current_claim_idx": 0}
    except Exception as e:
        logger.error(f"Claim extraction failed: {e}")
        return {"error": str(e)}


def classify_claim_node(state: AnalysisState) -> dict:
    """Classify the current claim against evidence."""
    idx = state["current_claim_idx"]
    claims = state["claims"]

    if idx >= len(claims):
        return {}

    claim_text = claims[idx]
    logger.info(f"Classifying claim {idx + 1}/{len(claims)}: {claim_text[:50]}...")

    try:
        result = classify_claim(
            claim_text=claim_text,
            company_id=state["company_id"],
            company_ticker=state["company_ticker"],
        )

        claim_result: ClaimResult = {
            "claim_text": claim_text,
            "claim_ordinal": idx,
            "status": result.status,
            "explanation": result.explanation,
            "quote": result.quote,
            "chunk_id": result.chunk_id,
            "similarity": None,
        }

        return {
            "results": [claim_result],
            "current_claim_idx": idx + 1,
        }

    except Exception as e:
        logger.error(f"Classification failed for claim {idx}: {e}")
        claim_result: ClaimResult = {
            "claim_text": claim_text,
            "claim_ordinal": idx,
            "status": "insufficient_evidence",
            "explanation": f"Classification error: {str(e)}",
            "quote": "",
            "chunk_id": None,
            "similarity": None,
        }
        return {
            "results": [claim_result],
            "current_claim_idx": idx + 1,
        }


def should_continue(state: AnalysisState) -> str:
    """Determine if we should continue classifying or end."""
    if state.get("error"):
        return END

    idx = state["current_claim_idx"]
    claims = state["claims"]

    if idx < len(claims):
        return "classify"
    return END


def build_analysis_graph() -> StateGraph:
    """Build the LangGraph for thesis analysis."""
    graph = StateGraph(AnalysisState)

    # Add nodes
    graph.add_node("extract", extract_claims_node)
    graph.add_node("classify", classify_claim_node)

    # Add edges
    graph.set_entry_point("extract")
    graph.add_edge("extract", "classify")
    graph.add_conditional_edges("classify", should_continue)

    return graph.compile()


# Compiled graph instance
analysis_pipeline = build_analysis_graph()


def run_analysis(
    thesis_id: str,
    thesis_text: str,
    company_id: str,
    company_ticker: str,
) -> list[ClaimResult]:
    """Run the full analysis pipeline.

    Args:
        thesis_id: UUID of the thesis
        thesis_text: The thesis text
        company_id: UUID of the company
        company_ticker: Ticker for display

    Returns:
        List of ClaimResult dicts with classification results
    """
    initial_state: AnalysisState = {
        "thesis_id": thesis_id,
        "thesis_text": thesis_text,
        "company_id": company_id,
        "company_ticker": company_ticker,
        "claims": [],
        "current_claim_idx": 0,
        "results": [],
        "error": None,
    }

    logger.info(f"Starting analysis pipeline for thesis {thesis_id}")

    try:
        final_state = analysis_pipeline.invoke(initial_state)

        if final_state.get("error"):
            logger.error(f"Pipeline error: {final_state['error']}")
            raise RuntimeError(final_state["error"])

        logger.info(f"Analysis complete: {len(final_state['results'])} claims processed")
        return final_state["results"]

    except Exception as e:
        logger.exception(f"Analysis pipeline failed: {e}")
        raise
