#!/usr/bin/env python3
"""ThesisLedger evaluation runner.

Scores the real pipeline — pgvector retrieval plus LLM classification — against
the hand-labelled verdicts in claims.json. Nothing here is simulated: every claim
is embedded, retrieved and classified exactly as a live analysis would do it.

Usage:
    python eval/runner.py                       # full set
    python eval/runner.py --ticker AAPL         # one company
    python eval/runner.py --limit 5             # first N claims
    python eval/runner.py --json results.json   # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CLAIMS = ROOT / "eval" / "claims.json"

VERDICTS = ("supported", "contradicted", "insufficient_evidence")


def setup_django() -> None:
    """Put backend/ on the path and boot Django so the ORM and RAG code import."""
    sys.path.insert(0, str(ROOT / "backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


@dataclass
class RetrievalMetric:
    """Ranking quality for one claim's retrieval step.

    Relevance is graded by cosine similarity from pgvector. There is no human
    relevance judgement per chunk, so a chunk counts as relevant when it clears
    `threshold` — this measures whether retrieval surfaced anything usable and
    how high up, not human-judged topical relevance.
    """

    claim_id: str
    similarities: list[float] = field(default_factory=list)
    threshold: float = 0.5
    top_k: int = 5

    def hit(self) -> bool:
        return any(s >= self.threshold for s in self.similarities[: self.top_k])

    def mrr(self) -> float:
        for i, s in enumerate(self.similarities[: self.top_k]):
            if s >= self.threshold:
                return 1.0 / (i + 1)
        return 0.0

    def ndcg(self) -> float:
        import math

        rels = [max(0.0, s) for s in self.similarities[: self.top_k]]
        if not rels:
            return 0.0
        dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rels))
        ideal = sorted(rels, reverse=True)
        idcg = sum(r / math.log2(i + 2) for i, r in enumerate(ideal))
        return dcg / idcg if idcg > 0 else 0.0


@dataclass
class ClaimResult:
    thesis_id: str
    claim_id: str
    ticker: str
    claim_text: str
    expected: str
    predicted: str
    correct: bool
    quote: str
    quote_verified: bool
    explanation: str
    retrieval: Optional[RetrievalMetric]
    elapsed_s: float
    error: Optional[str] = None


class Evaluator:
    def __init__(self, claims_file: Path, k: int = 5):
        self.claims_file = claims_file
        self.k = k
        self.results: list[ClaimResult] = []

    def load(self) -> list[dict[str, Any]]:
        try:
            # utf-8-sig so a stray byte-order mark does not break the parse.
            with open(self.claims_file, encoding="utf-8-sig") as f:
                data = json.load(f)
        except FileNotFoundError:
            sys.exit(f"error: {self.claims_file} not found")
        except json.JSONDecodeError as e:
            sys.exit(f"error: cannot parse {self.claims_file}: {e}")

        theses = data.get("thesis_claims", [])
        if not theses:
            sys.exit("error: claims.json has no thesis_claims")
        return theses

    def evaluate_claim(self, thesis: dict, claim: dict, company) -> ClaimResult:
        from apps.ingestion.search import search_chunks_real
        from apps.rag.classification import classify_claim

        started = time.time()
        text = claim["text"]

        try:
            chunks = search_chunks_real(str(company.id), text, k=self.k)
            # pgvector annotates cosine *distance*; similarity is its complement.
            # The stub fallback returns chunks with neither, hence the getattr.
            sims = []
            for c in chunks:
                dist = getattr(c, "distance", None)
                sims.append(
                    1.0 - float(dist) if dist is not None else float(getattr(c, "similarity", 0.0) or 0.0)
                )
            retrieval = RetrievalMetric(
                claim_id=claim["claim_id"], similarities=sims, top_k=self.k
            )

            result = classify_claim(
                claim_text=text,
                company_id=str(company.id),
                company_ticker=company.ticker,
                k=self.k,
            )

            predicted = result.status
            quote = result.quote or ""
            # classify_claim downgrades to insufficient_evidence when a quote
            # cannot be found verbatim, so a surviving quote is a verified one.
            verified = bool(quote) and predicted != "insufficient_evidence"

            return ClaimResult(
                thesis_id=thesis["thesis_id"],
                claim_id=claim["claim_id"],
                ticker=thesis.get("ticker", company.ticker),
                claim_text=text,
                expected=claim["expected_verdict"],
                predicted=predicted,
                correct=predicted == claim["expected_verdict"],
                quote=quote,
                quote_verified=verified,
                explanation=result.explanation or "",
                retrieval=retrieval,
                elapsed_s=time.time() - started,
            )

        except Exception as e:
            return ClaimResult(
                thesis_id=thesis["thesis_id"],
                claim_id=claim["claim_id"],
                ticker=thesis.get("ticker", ""),
                claim_text=text,
                expected=claim["expected_verdict"],
                predicted="error",
                correct=False,
                quote="",
                quote_verified=False,
                explanation="",
                retrieval=None,
                elapsed_s=time.time() - started,
                error=str(e),
            )

    def run(self, ticker: Optional[str] = None, limit: Optional[int] = None) -> None:
        from apps.ledger.models import Company

        theses = self.load()
        if ticker:
            theses = [t for t in theses if t.get("ticker", "").upper() == ticker.upper()]
            if not theses:
                sys.exit(f"error: no theses for ticker {ticker}")

        seen = 0
        for thesis in theses:
            tk = thesis.get("ticker")
            company = Company.objects.filter(ticker=tk).first()
            if not company:
                print(f"  skip {thesis['thesis_id']}: no Company row for {tk}", flush=True)
                continue

            print(f"\n{thesis['thesis_id']} ({tk})", flush=True)
            for claim in thesis["claims"]:
                if limit is not None and seen >= limit:
                    return
                res = self.evaluate_claim(thesis, claim, company)
                self.results.append(res)
                seen += 1

                mark = "✓" if res.correct else "✗"
                if res.error:
                    print(f"  ! {res.claim_id}: {res.error[:70]}", flush=True)
                else:
                    print(
                        f"  {mark} {res.claim_id}: expected {res.expected}, "
                        f"got {res.predicted} ({res.elapsed_s:.1f}s)",
                        flush=True,
                    )

    # --- metrics -----------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        scored = [r for r in self.results if not r.error]
        errors = [r for r in self.results if r.error]
        total = len(scored)

        if not total:
            return {"total": 0, "errors": len(errors)}

        correct = sum(1 for r in scored if r.correct)

        per_class: dict[str, dict[str, int]] = {
            v: {"tp": 0, "fp": 0, "fn": 0} for v in VERDICTS
        }
        for r in scored:
            if r.predicted == r.expected:
                per_class.setdefault(r.expected, {"tp": 0, "fp": 0, "fn": 0})["tp"] += 1
            else:
                per_class.setdefault(r.predicted, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1
                per_class.setdefault(r.expected, {"tp": 0, "fp": 0, "fn": 0})["fn"] += 1

        for v, c in per_class.items():
            p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
            rec = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0
            c["precision"] = round(p, 3)
            c["recall"] = round(rec, 3)
            c["f1"] = round(2 * p * rec / (p + rec), 3) if p + rec else 0.0

        rets = [r.retrieval for r in scored if r.retrieval and r.retrieval.similarities]
        cited = [r for r in scored if r.predicted != "insufficient_evidence"]

        return {
            "total": total,
            "errors": len(errors),
            "accuracy": round(correct / total, 3),
            "per_class": per_class,
            "retrieval": {
                "hit_rate": round(sum(m.hit() for m in rets) / len(rets), 3) if rets else 0.0,
                "mrr": round(sum(m.mrr() for m in rets) / len(rets), 3) if rets else 0.0,
                "ndcg": round(sum(m.ndcg() for m in rets) / len(rets), 3) if rets else 0.0,
                "claims_with_retrieval": len(rets),
            },
            "citation": {
                "verdicts_with_citation": len(cited),
                "quote_verified_rate": (
                    round(sum(1 for r in cited if r.quote_verified) / len(cited), 3)
                    if cited
                    else 0.0
                ),
            },
            "latency": {
                "mean_s": round(sum(r.elapsed_s for r in scored) / total, 2),
                "max_s": round(max(r.elapsed_s for r in scored), 2),
            },
        }

    def report(self, summary: dict[str, Any]) -> None:
        print("\n" + "=" * 68)
        print("EVALUATION SUMMARY")
        print("=" * 68)

        if not summary.get("total"):
            print("No claims scored.")
            if summary.get("errors"):
                print(f"{summary['errors']} claim(s) errored.")
            return

        print(f"Claims scored     : {summary['total']}  (errors: {summary['errors']})")
        print(f"Accuracy          : {summary['accuracy']:.1%}")

        r = summary["retrieval"]
        print(f"Retrieval hit@{self.k}   : {r['hit_rate']:.1%}")
        print(f"Retrieval MRR     : {r['mrr']:.3f}")
        print(f"Retrieval NDCG    : {r['ndcg']:.3f}")

        c = summary["citation"]
        print(f"Quote verified    : {c['quote_verified_rate']:.1%} of {c['verdicts_with_citation']} cited verdicts")

        lat = summary["latency"]
        print(f"Latency per claim : {lat['mean_s']:.1f}s mean, {lat['max_s']:.1f}s max")

        print("\nPer-verdict:")
        print(f"  {'verdict':<24} {'P':>6} {'R':>6} {'F1':>6}")
        for v in VERDICTS:
            m = summary["per_class"].get(v, {})
            print(
                f"  {v:<24} {m.get('precision', 0):>6.2f} "
                f"{m.get('recall', 0):>6.2f} {m.get('f1', 0):>6.2f}"
            )

        wrong = [x for x in self.results if not x.correct and not x.error]
        if wrong:
            print(f"\nMisclassified ({len(wrong)}):")
            for x in wrong[:10]:
                print(f"  {x.claim_id}: {x.expected} → {x.predicted}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument("--ticker", help="Evaluate a single company")
    parser.add_argument("--limit", type=int, help="Stop after N claims")
    parser.add_argument("-k", type=int, default=5, help="Chunks retrieved per claim")
    parser.add_argument("--json", type=Path, help="Write results as JSON")
    args = parser.parse_args()

    setup_django()

    ev = Evaluator(args.claims, k=args.k)
    started = time.time()
    ev.run(ticker=args.ticker, limit=args.limit)
    summary = ev.summary()
    ev.report(summary)
    print(f"\nCompleted in {time.time() - started:.1f}s")

    if args.json:
        payload = {
            "summary": summary,
            "results": [
                {**asdict(r), "retrieval": asdict(r.retrieval) if r.retrieval else None}
                for r in ev.results
            ],
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {args.json}")

    return 0 if summary.get("total") else 1


if __name__ == "__main__":
    sys.exit(main())
