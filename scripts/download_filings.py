#!/usr/bin/env python3
"""Download SEC 10-K filings for the target companies.

Writes the primary 10-K HTML document per filing to data/raw/{TICKER}/, which is
what apps.ingestion expects: the cleaner parses HTML and the ingest_filings
command globs *.htm*.

SEC EDGAR requires a User-Agent carrying a real contact email, otherwise it
returns 403. Set SEC_USER_AGENT, e.g.:

    SEC_USER_AGENT="ThesisLedger/0.1 (you@example.com)" python scripts/download_filings.py
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SEC_TICKER_MAP = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{document}"

# Five companies, one filing each. Sized for the demo: embedding is CPU-bound
# through Ollama at roughly 35 chunks/min, so a 10-company two-year corpus would
# take about 3.5 hours to index. This one takes well under an hour.
# Must stay in sync with COMPANIES in seed_companies.py.
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "NVDA",   # Technology
    "V",                      # Financials
    "XOM",                    # Energy
]

# Curated CIKs, same values as COMPANIES in seed_companies.py. These win over
# SEC's ticker map, which tracks the *current* registrant for a symbol and can
# point at a freshly reorganised entity with no filing history — as of 2026 it
# maps XOM to ExxonMobil Holdings Corp (CIK 2115436), which has never filed a
# 10-K, instead of Exxon Mobil Corp (CIK 34088), which has decades of them.
CIK_OVERRIDES = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "NVDA": "0001045810",
    "JPM": "0000019617",
    "V": "0001403161",
    "UNH": "0000731766",
    "LLY": "0000059478",
    "WMT": "0000104169",
    "KO": "0000021344",
    "XOM": "0000034088",
}

RATE_LIMIT_DELAY = 0.5  # SEC asks for 10 req/s max; 0.5s per request is well under
TIMEOUT = 30

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw"


class SECDownloader:
    def __init__(self, output_dir: Path, user_agent: str):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        )
        self._ticker_map: Optional[dict[str, str]] = None

    def _get(self, url: str) -> requests.Response:
        time.sleep(RATE_LIMIT_DELAY)
        resp = self.session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp

    def ticker_to_cik(self, ticker: str) -> Optional[str]:
        """Resolve a ticker to a zero-padded 10-digit CIK, curated list first."""
        if ticker.upper() in CIK_OVERRIDES:
            return CIK_OVERRIDES[ticker.upper()]

        if self._ticker_map is None:
            data = self._get(SEC_TICKER_MAP).json()
            self._ticker_map = {
                row["ticker"].upper(): str(row["cik_str"]).zfill(10)
                for row in data.values()
            }
            logger.info("Loaded CIK map for %d tickers", len(self._ticker_map))
        return self._ticker_map.get(ticker.upper())

    def list_10k_filings(self, cik: str, limit: int) -> list[dict]:
        """Return metadata for the most recent 10-K filings, newest first."""
        data = self._get(SEC_SUBMISSIONS.format(cik=cik)).json()
        recent = data["filings"]["recent"]

        filings = []
        for i, form in enumerate(recent["form"]):
            if form != "10-K":
                continue
            filings.append(
                {
                    "accession": recent["accessionNumber"][i],
                    "document": recent["primaryDocument"][i],
                    "report_date": recent["reportDate"][i],
                    "filing_date": recent["filingDate"][i],
                }
            )
            if len(filings) >= limit:
                break
        return filings

    def download(self, ticker: str, cik: str, filing: dict) -> Optional[Path]:
        """Fetch one filing's primary document. Returns the path, or None if skipped."""
        year = filing["report_date"][:4]
        ticker_dir = self.output_dir / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)

        # Stable name — no timestamp — so re-running is idempotent instead of
        # producing a fresh copy of identical content every time.
        target = ticker_dir / f"10k_{year}.htm"
        if target.exists():
            logger.info("  %s already present, skipping", target.name)
            return None

        url = SEC_ARCHIVE.format(
            cik_int=int(cik),
            accession=filing["accession"].replace("-", ""),
            document=filing["document"],
        )
        resp = self._get(url)
        target.write_text(resp.text, encoding="utf-8")

        meta = ticker_dir / f"10k_{year}.meta.json"
        meta.write_text(
            json.dumps(
                {
                    "ticker": ticker,
                    "cik": cik,
                    "accession_number": filing["accession"],
                    "period_end": filing["report_date"],
                    "filed_at": filing["filing_date"],
                    "source_url": url,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        size_kb = len(resp.content) / 1024
        logger.info("  %s (%.0f KB)", target.name, size_kb)
        return target

    def run(self, tickers: list[str], per_ticker: int) -> tuple[int, int]:
        downloaded = 0
        failed_tickers = 0

        for ticker in tickers:
            logger.info("%s", ticker)
            try:
                cik = self.ticker_to_cik(ticker)
                if not cik:
                    logger.warning("  no CIK for %s, skipping", ticker)
                    failed_tickers += 1
                    continue

                filings = self.list_10k_filings(cik, per_ticker)
                if not filings:
                    logger.warning("  no 10-K filings found for %s", ticker)
                    failed_tickers += 1
                    continue

                for filing in filings:
                    if self.download(ticker, cik, filing):
                        downloaded += 1

            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else "?"
                if status == 403:
                    logger.error("  403 from SEC — check SEC_USER_AGENT has a real email")
                else:
                    logger.error("  HTTP %s for %s", status, ticker)
                failed_tickers += 1
            except Exception as e:
                logger.error("  failed for %s: %s", ticker, e)
                failed_tickers += 1

        return downloaded, failed_tickers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument(
        "--per-ticker", type=int, default=1, help="How many recent 10-Ks per company"
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--user-agent", default=os.getenv("SEC_USER_AGENT", ""))
    args = parser.parse_args()

    if "@" not in args.user_agent:
        logger.error(
            "SEC requires a contact email in the User-Agent. Set SEC_USER_AGENT, e.g.\n"
            '  SEC_USER_AGENT="ThesisLedger/0.1 (you@example.com)"'
        )
        return 2

    downloader = SECDownloader(args.output_dir, args.user_agent)
    downloaded, failed = downloader.run(args.tickers, args.per_ticker)

    logger.info("")
    logger.info("Downloaded %d filings; %d tickers failed", downloaded, failed)
    logger.info("Output: %s", args.output_dir)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
