"""Claim classification against SEC filing evidence.

Uses LangChain RAG to retrieve relevant chunks and classify claims as
supported, contradicted, or insufficient_evidence.

LangChain components used:
- ChatOllama: LLM wrapper for Ollama
- ChatPromptTemplate: Structured prompts
- StrOutputParser: Output parsing
- RunnablePassthrough: Chain composition
- Custom retriever wrapping pgvector search
"""

import logging
from typing import Literal, Optional

from django.conf import settings
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from apps.ingestion.search import search_chunks_real

logger = logging.getLogger(__name__)


class ChunkRetriever:
    """LangChain-compatible retriever wrapping pgvector search.

    Converts database Chunk objects to LangChain Documents for use
    in retrieval chains.
    """

    def __init__(self, company_id: str, k: int = 5):
        self.company_id = company_id
        self.k = k

    def get_relevant_documents(self, query: str) -> list[Document]:
        """Retrieve relevant chunks as LangChain Documents."""
        chunks = search_chunks_real(self.company_id, query, k=self.k)

        documents = []
        for chunk in chunks:
            metadata = {
                "chunk_id": str(chunk.id),
                "section": chunk.section,
                "filing_type": chunk.filing.filing_type,
                "period_end": str(chunk.filing.period_end),
                "source_url": chunk.filing.source_url,
            }
            doc = Document(page_content=chunk.text, metadata=metadata)
            documents.append(doc)

        return documents

    def invoke(self, query: str) -> list[Document]:
        """Invoke retriever (for LCEL compatibility)."""
        return self.get_relevant_documents(query)


class ClassificationResult(BaseModel):
    """Structured output for claim classification."""

    status: Literal["supported", "contradicted", "insufficient_evidence"] = Field(
        description="Whether the claim is supported, contradicted, or has insufficient evidence"
    )
    explanation: str = Field(
        description="1-2 sentence explanation of the classification"
    )
    quote: str = Field(
        description="Exact quote from the filing that supports the classification (empty if insufficient_evidence)"
    )
    chunk_id: Optional[str] = Field(
        default=None,
        description="ID of the chunk containing the quote"
    )


CLASSIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a financial analyst verifying investment claims against SEC filings.

Given a claim and evidence from SEC filings, determine if the claim is:
- "supported": The evidence clearly supports the claim
- "contradicted": The evidence contradicts or disproves the claim
- "insufficient_evidence": The evidence doesn't directly address the claim

IMPORTANT:
- Only use "supported" if there's clear evidence FOR the claim
- Only use "contradicted" if there's clear evidence AGAINST the claim
- Use "insufficient_evidence" if the passages don't directly address the claim
- The quote MUST be an exact substring from the provided evidence
- If insufficient_evidence, leave quote empty"""),
    ("human", """Claim to verify:
{claim}

Evidence from {company} SEC filings:
---
{evidence}
---

Classify this claim based on the evidence provided."""),
])


def get_llm(model: Optional[str] = None) -> ChatOllama:
    """Get configured LLM instance."""
    return ChatOllama(
        model=model or settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_URL,
        temperature=0.0,
        format="json",
    )


def classify_claim(
    claim_text: str,
    company_id: str,
    company_ticker: str,
    k: int = 5,
) -> ClassificationResult:
    """Classify a claim against SEC filing evidence.

    Args:
        claim_text: The claim to verify
        company_id: UUID of the company
        company_ticker: Ticker for display
        k: Number of chunks to retrieve

    Returns:
        ClassificationResult with status, explanation, and quote
    """
    # Retrieve relevant chunks
    chunks = search_chunks_real(company_id, claim_text, k=k)

    if not chunks:
        logger.warning(f"No chunks found for claim classification: {claim_text[:50]}...")
        return ClassificationResult(
            status="insufficient_evidence",
            explanation="No relevant passages found in the company's SEC filings.",
            quote="",
            chunk_id=None,
        )

    # Format evidence for prompt
    evidence_parts = []
    chunk_map = {}
    for i, chunk in enumerate(chunks):
        chunk_map[str(i)] = chunk
        section_info = f"[{chunk.section}]" if chunk.section else ""
        evidence_parts.append(f"Passage {i+1} {section_info}:\n{chunk.text}")

    evidence_text = "\n\n".join(evidence_parts)

    try:
        llm = get_llm()
        chain = CLASSIFICATION_PROMPT | llm.with_structured_output(ClassificationResult)

        result = chain.invoke({
            "claim": claim_text,
            "company": company_ticker,
            "evidence": evidence_text,
        })

        # Verify quote exists in chunks (prevent hallucination)
        if result.status != "insufficient_evidence" and result.quote:
            quote_found = False
            for chunk in chunks:
                if result.quote in chunk.text:
                    result.chunk_id = str(chunk.id)
                    quote_found = True
                    break

            if not quote_found:
                logger.warning("Quote not found in chunks, downgrading to insufficient_evidence")
                result.status = "insufficient_evidence"
                result.quote = ""
                result.chunk_id = None
                result.explanation = f"Classification attempted but quote could not be verified. Original assessment: {result.explanation}"

        logger.info(f"Classified claim as {result.status}: {claim_text[:50]}...")
        return result

    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return ClassificationResult(
            status="insufficient_evidence",
            explanation=f"Classification failed due to error: {str(e)}",
            quote="",
            chunk_id=None,
        )


def classify_claim_simple(
    claim_text: str,
    evidence_text: str,
    company_ticker: str,
) -> ClassificationResult:
    """Classify with pre-fetched evidence (for testing/pipeline use)."""
    try:
        llm = get_llm()
        chain = CLASSIFICATION_PROMPT | llm.with_structured_output(ClassificationResult)

        result = chain.invoke({
            "claim": claim_text,
            "company": company_ticker,
            "evidence": evidence_text,
        })
        return result

    except Exception as e:
        logger.error(f"Simple classification failed: {e}")
        return ClassificationResult(
            status="insufficient_evidence",
            explanation=str(e),
            quote="",
            chunk_id=None,
        )


def build_rag_chain(company_id: str, company_ticker: str, k: int = 5):
    """Build a LangChain RAG chain for claim classification.

    Uses LCEL (LangChain Expression Language) to compose:
    1. Retriever: ChunkRetriever wrapping pgvector
    2. Prompt: Classification prompt template
    3. LLM: ChatOllama with structured output

    Args:
        company_id: UUID of company to search
        company_ticker: Ticker for display in prompt
        k: Number of chunks to retrieve

    Returns:
        Runnable chain that takes claim text and returns ClassificationResult
    """
    retriever = ChunkRetriever(company_id, k=k)
    llm = get_llm()

    def format_docs(docs: list[Document]) -> str:
        """Format retrieved documents for the prompt."""
        parts = []
        for i, doc in enumerate(docs):
            section = doc.metadata.get("section", "")
            section_info = f"[{section}]" if section else ""
            parts.append(f"Passage {i+1} {section_info}:\n{doc.page_content}")
        return "\n\n".join(parts)

    # Build the chain using LCEL
    chain = (
        {
            "claim": RunnablePassthrough(),
            "company": lambda _: company_ticker,
            "evidence": lambda x: format_docs(retriever.invoke(x)),
        }
        | CLASSIFICATION_PROMPT
        | llm.with_structured_output(ClassificationResult)
    )

    return chain


def classify_with_chain(
    claim_text: str,
    company_id: str,
    company_ticker: str,
    k: int = 5,
) -> ClassificationResult:
    """Classify using LangChain RAG chain.

    Alternative to classify_claim() that uses pure LangChain composition.
    Demonstrates LCEL pattern for RAG.

    Args:
        claim_text: Claim to verify
        company_id: UUID of company
        company_ticker: Ticker for display
        k: Number of chunks to retrieve

    Returns:
        ClassificationResult with status, explanation, quote
    """
    try:
        chain = build_rag_chain(company_id, company_ticker, k)
        result = chain.invoke(claim_text)

        # Note: This version doesn't do quote verification
        # Use classify_claim() for production with verification
        logger.info(f"Chain classified claim as {result.status}")
        return result

    except Exception as e:
        logger.error(f"Chain classification failed: {e}")
        return ClassificationResult(
            status="insufficient_evidence",
            explanation=f"Classification error: {str(e)}",
            quote="",
            chunk_id=None,
        )
