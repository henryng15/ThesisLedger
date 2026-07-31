"""Claim extraction from investment theses using LangChain.

Extracts up to 5 testable, specific claims from a thesis statement
using structured output from Ollama via LangChain.

LangChain components used:
- ChatOllama: LLM wrapper for local Ollama
- ChatPromptTemplate: Structured prompt templates
- with_structured_output: Pydantic schema enforcement
- RunnableSequence: Chain composition (LCEL)
"""

import logging
from typing import Optional

from django.conf import settings

from apps.core.ollama import ollama_headers
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ClaimDraft(BaseModel):
    """A single extracted claim."""

    text: str = Field(description="A specific, testable claim that can be verified against SEC filings")


class ClaimsOutput(BaseModel):
    """Structured output for claim extraction."""

    claims: list[ClaimDraft] = Field(
        description="List of testable claims (max 5)",
        max_length=5,
    )


EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a financial analyst extracting testable claims from investment theses.

Given a thesis about a company, extract up to 5 specific, testable claims that could be verified against the company's SEC filings (10-K, 10-Q).

Each claim should be:
- Specific and measurable (not vague)
- Verifiable against financial statements or MD&A
- Focused on one aspect of the thesis

Return claims in order of importance to the thesis."""),
    ("human", """Company: {company}

Investment Thesis:
{thesis_text}

Extract the key testable claims from this thesis."""),
])


def get_llm(model: Optional[str] = None) -> ChatOllama:
    """Get configured LLM instance."""
    return ChatOllama(
        model=model or settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_URL,
        # Ollama sits behind a token-authenticated gateway when it runs off-host.
        client_kwargs={"headers": ollama_headers()},
        temperature=0.1,
        format="json",
    )


def generate_claims_llm(thesis_text: str, company_ticker: str) -> list[str]:
    """Extract claims from thesis using LLM.

    Args:
        thesis_text: The investment thesis text
        company_ticker: Company ticker symbol for context

    Returns:
        List of claim text strings (max 5)
    """
    try:
        llm = get_llm()
        chain = EXTRACTION_PROMPT | llm.with_structured_output(ClaimsOutput)

        result = chain.invoke({
            "thesis_text": thesis_text,
            "company": company_ticker,
        })

        claims = [claim.text for claim in result.claims[:5]]
        logger.info(f"Extracted {len(claims)} claims for {company_ticker}")
        return claims

    except Exception as e:
        logger.error(f"LLM claim extraction failed: {e}")
        # Fallback to simple extraction
        return generate_claims_fallback(thesis_text)


def generate_claims_fallback(thesis_text: str) -> list[str]:
    """Simple fallback claim extraction when LLM fails.

    Splits thesis into sentences and picks the most substantive ones.
    """
    import re

    sentences = re.split(r"[.!?]+", thesis_text)
    claims = []

    for sent in sentences:
        sent = sent.strip()
        # Keep sentences that look like claims (have numbers or comparisons)
        if len(sent) > 30 and any(
            word in sent.lower()
            for word in ["revenue", "growth", "margin", "increase", "decrease", "market", "profit"]
        ):
            claims.append(sent)
            if len(claims) >= 5:
                break

    # If we found nothing, just use first 3 sentences
    if not claims:
        claims = [s.strip() for s in sentences[:3] if len(s.strip()) > 20]

    return claims[:5]


def build_extraction_chain() -> RunnableSequence:
    """Build a LangChain extraction chain using LCEL.

    Returns a reusable chain that can be invoked with thesis/company.

    Returns:
        RunnableSequence that takes dict and returns ClaimsOutput
    """
    llm = get_llm()
    chain = EXTRACTION_PROMPT | llm.with_structured_output(ClaimsOutput)
    return chain


def generate_claims_with_chain(thesis_text: str, company_ticker: str) -> list[str]:
    """Extract claims using pre-built LangChain chain.

    Alternative entry point showing chain reuse pattern.

    Args:
        thesis_text: Investment thesis text
        company_ticker: Company ticker for context

    Returns:
        List of extracted claim strings
    """
    try:
        chain = build_extraction_chain()
        result = chain.invoke({
            "thesis_text": thesis_text,
            "company": company_ticker,
        })
        return [claim.text for claim in result.claims[:5]]

    except Exception as e:
        logger.error(f"Chain extraction failed: {e}")
        return generate_claims_fallback(thesis_text)
