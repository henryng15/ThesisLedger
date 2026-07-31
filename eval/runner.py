#!/usr/bin/env python3
"""
RAG Evaluation Runner for ThesisLedger

Loads evaluation pairs from eval/claims.json and measures:
- Retrieval hit-rate: % of claims that returned relevant chunks
- Classification accuracy: relevance of retrieved chunks to claims
- Coverage metrics: availability of indexed chunks per ticker
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

# Setup Django (must be before any Django imports)
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.db.models import F
from django.conf import settings
from apps.ledger.models import Chunk, Company, Claim, Thesis, AnalysisJob
from apps.ledger.embeddings import build_embedding_service, EmbeddingServiceError


class RAGEvaluator:
    def __init__(self, eval_data_path: Path, top_k: int = 5):
        self.eval_data_path = eval_data_path
        self.top_k = top_k
        self.embedding_service = build_embedding_service()
        self.results = {
            "total_claims": 0,
            "successful_retrievals": 0,
            "failed_retrievals": 0,
            "coverage": {},
            "retrieval_metrics": [],
            "claim_results": [],
        }

    def load_evaluation_data(self) -> list[dict[str, str]]:
        """Load claims.json evaluation pairs."""
        with open(self.eval_data_path, "r") as f:
            data = json.load(f)
        return data

    def get_company_chunks(self, ticker: str) -> list[Chunk]:
        """Retrieve all chunks for a given ticker."""
        try:
            company = Company.objects.filter(ticker=ticker, is_active=True).first()
            if not company:
                return []
            return list(company.filings.prefetch_related("chunks").all())
        except Exception as e:
            print(f"Error fetching chunks for {ticker}: {e}")
            return []

    def search_chunks(self, claim_text: str, company: Company, k: int = None) -> list[dict[str, Any]]:
        """
        Search for relevant chunks using vector similarity.

        Returns list of dicts with: chunk, similarity, filing_info
        """
        if k is None:
            k = self.top_k

        try:
            # Generate embedding for claim
            claim_embedding = self.embedding_service.embed_text(claim_text)
        except EmbeddingServiceError as e:
            print(f"  ✗ Embedding generation failed: {e}")
            return []

        try:
            # Query pgvector for nearest neighbors
            chunks = Chunk.objects.filter(
                filing__company=company,
                embedding__isnull=False,
            ).annotate(
                # Calculate cosine similarity using pgvector
                similarity=F("embedding").cosine_similarity(claim_embedding)
            ).order_by("-similarity")[:k]

            results = []
            for chunk in chunks:
                results.append({
                    "chunk": chunk,
                    "similarity": chunk.similarity,
                    "section": chunk.section,
                    "ordinal": chunk.ordinal,
                    "filing_id": str(chunk.filing_id),
                    "filing_type": chunk.filing.filing_type,
                    "period_end": chunk.filing.period_end,
                })

            return results
        except Exception as e:
            print(f"  ✗ Vector search failed: {e}")
            return []

    def calculate_hit_rate(self, search_results: list[dict]) -> float:
        """
        Calculate hit-rate: whether any relevant chunks were found.
        A hit is defined as a chunk with similarity > 0.5
        """
        if not search_results:
            return 0.0

        relevant = sum(1 for r in search_results if r.get("similarity", 0) > 0.5)
        return relevant / len(search_results) if search_results else 0.0

    def format_output(self):
        """Pretty-print evaluation results."""
        print("\n" + "=" * 80)
        print("ThesisLedger RAG Evaluation Results")
        print("=" * 80)

        # Summary statistics
        print(f"\n📊 Summary")
        print("─" * 80)
        print(f"Total claims evaluated:     {self.results['total_claims']}")
        print(f"Successful retrievals:      {self.results['successful_retrievals']} ({self.success_rate:.1f}%)")
        print(f"Failed retrievals:          {self.results['failed_retrievals']} ({100 - self.success_rate:.1f}%)")

        # Retrieval metrics
        if self.results["retrieval_metrics"]:
            metrics = self.results["retrieval_metrics"]
            avg_similarity = sum(m["max_similarity"] for m in metrics if m["max_similarity"] > 0) / max(1, sum(1 for m in metrics if m["max_similarity"] > 0))
            avg_hit_rate = sum(m["hit_rate"] for m in metrics) / len(metrics)
            above_threshold = sum(1 for m in metrics if m["max_similarity"] > 0.5)

            print(f"\n🎯 Retrieval Quality")
            print("─" * 80)
            print(f"Average max similarity:     {avg_similarity:.3f}")
            print(f"Average hit-rate (>0.5):    {avg_hit_rate:.1f}%")
            print(f"Claims above threshold:     {above_threshold}/{len(metrics)} ({above_threshold*100//len(metrics)}%)")
            print(f"Top-k for search:           {self.top_k}")

        # Coverage by ticker
        if self.results["coverage"]:
            print(f"\n📈 Coverage by Ticker")
            print("─" * 80)
            for ticker, info in sorted(self.results["coverage"].items()):
                status = "✓" if info["chunk_count"] > 0 else "✗"
                print(f"{status} {ticker:6s}  {info['chunk_count']:4d} chunks  {info['filing_count']} filings")

        # Detailed results
        if self.results["claim_results"]:
            print(f"\n📋 Detailed Results (Top Findings)")
            print("─" * 80)
            for i, result in enumerate(self.results["claim_results"][:10], 1):
                claim = result["claim"]
                search = result["search_results"]

                print(f"\n{i}. {claim['target_ticker']} - {claim['expected_claim'][:70]}")

                if search:
                    top = search[0]
                    print(f"   ✓ Retrieved: similarity={top['similarity']:.3f}")
                    print(f"     Section: {top['section'] or 'Unknown'}")
                    print(f"     Filing: {top['filing_type']} ({top['period_end']})")
                else:
                    print(f"   ✗ No results returned")

        print("\n" + "=" * 80 + "\n")

    def run(self):
        """Execute the evaluation pipeline."""
        evaluation_data = self.load_evaluation_data()
        self.results["total_claims"] = len(evaluation_data)

        print(f"\n🚀 Starting RAG Evaluation ({len(evaluation_data)} claims)\n")

        for idx, eval_pair in enumerate(evaluation_data, 1):
            thesis = eval_pair["thesis"]
            claim = eval_pair["expected_claim"]
            ticker = eval_pair["target_ticker"]

            # Get company
            company = Company.objects.filter(ticker=ticker, is_active=True).first()
            if not company:
                print(f"[{idx:2d}/{len(evaluation_data)}] ✗ {ticker:6s} - Company not found")
                self.results["failed_retrievals"] += 1
                self.results["coverage"][ticker] = {"chunk_count": 0, "filing_count": 0}
                continue

            # Initialize coverage tracking
            if ticker not in self.results["coverage"]:
                filings = list(company.filings.all())
                chunk_count = sum(f.chunks.count() for f in filings)
                self.results["coverage"][ticker] = {
                    "chunk_count": chunk_count,
                    "filing_count": len(filings),
                }

            # Skip if no chunks available
            if self.results["coverage"][ticker]["chunk_count"] == 0:
                print(f"[{idx:2d}/{len(evaluation_data)}] ⊘ {ticker:6s} - No indexed chunks")
                self.results["failed_retrievals"] += 1
                continue

            # Perform vector search
            search_results = self.search_chunks(claim, company, k=self.top_k)

            if search_results:
                max_similarity = search_results[0]["similarity"]
                hit_rate = self.calculate_hit_rate(search_results)

                self.results["successful_retrievals"] += 1
                status = "✓" if max_similarity > 0.5 else "⊘"

                print(f"[{idx:2d}/{len(evaluation_data)}] {status} {ticker:6s} - "
                      f"sim={max_similarity:.3f} hit={hit_rate:.1f}% | {claim[:55]}...")

                self.results["retrieval_metrics"].append({
                    "ticker": ticker,
                    "claim": claim,
                    "max_similarity": max_similarity,
                    "hit_rate": hit_rate,
                    "result_count": len(search_results),
                })
            else:
                self.results["failed_retrievals"] += 1
                print(f"[{idx:2d}/{len(evaluation_data)}] ✗ {ticker:6s} - Retrieval failed")

            # Store detailed results
            self.results["claim_results"].append({
                "claim": eval_pair,
                "search_results": search_results,
            })

        self.success_rate = (
            self.results["successful_retrievals"] * 100 / self.results["total_claims"]
            if self.results["total_claims"] > 0 else 0
        )
        self.format_output()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Evaluate RAG pipeline on thesis-claim pairs"
    )
    parser.add_argument(
        "--eval-data",
        type=Path,
        default=Path(__file__).parent / "claims.json",
        help="Path to evaluation claims JSON (default: eval/claims.json)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of chunks to retrieve per claim (default: 5)",
    )

    args = parser.parse_args()

    if not args.eval_data.exists():
        print(f"❌ Evaluation data not found: {args.eval_data}")
        sys.exit(1)

    evaluator = RAGEvaluator(args.eval_data, top_k=args.top_k)
    evaluator.run()


if __name__ == "__main__":
    main()
