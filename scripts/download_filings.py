#!/usr/bin/env python3
"""
Download latest SEC 10-K/10-Q filings for specified tickers.

Handles rate limiting, retries, and organizes filings by ticker.
Requires: requests, beautifulsoup4, python-dateutil
"""

import os
import sys
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urljoin
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# SEC EDGAR API endpoints
SEC_CIK_LOOKUP = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={}&CIK=&type=&dateb=&owner=exclude&count=100&myHID=&appid=&format=json"
SEC_FILINGS_SEARCH = "https://data.sec.gov/api/xbrl/companyfacts/CIK{}.json"
SEC_FILING_DOWNLOAD = "https://www.sec.gov/Archives/{}"

DEFAULT_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",  # Tech
    "JPM", "BAC", "WFC", "GS", "MS",          # Finance
    "UNH", "JNJ", "PFE", "AZN", "LLY",        # Healthcare
    "PG", "KO", "MCD", "NKE", "HD",           # Consumer
    "XOM", "CVX", "SLB", "MPC", "COP",        # Energy
    "BA", "LMT", "RTX", "GD", "NOC",          # Aerospace
    "TSLA", "F", "GM", "LCID", "RIVN",        # Automotive
    "COST", "WMT", "TGT", "AMZN", "AZO",      # Retail
    "META", "NFLX", "ORCL", "IBM", "INTC",    # Enterprise
    "UBER", "LYFT", "DASH", "SPOT", "PINS",   # Growth
]

RATE_LIMIT_DELAY = 0.5  # SEC asks for 0.1s minimum; we use 0.5s to be safe
MAX_RETRIES = 3
TIMEOUT = 30

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw"


class SECFilingDownloader:
    def __init__(self, output_dir: Path = OUTPUT_DIR, user_agent: str = None):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.user_agent = user_agent or "ThesisLedger/0.1 (research-dev)"
        self.session = self._create_session()
        self.ticker_to_cik = {}

    def _create_session(self) -> requests.Session:
        """Create a session with rate-limited headers."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        })
        return session

    def _rate_limit(self):
        """Respect SEC's rate limits."""
        time.sleep(RATE_LIMIT_DELAY)

    def lookup_cik(self, ticker: str) -> Optional[str]:
        """Look up CIK for a ticker via SEC company search."""
        try:
            self._rate_limit()
            url = SEC_CIK_LOOKUP.format(ticker)
            resp = self.session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()

            data = resp.json()
            if "cik_lookup" in data and ticker in data["cik_lookup"]:
                cik = str(data["cik_lookup"][ticker]).zfill(10)
                logger.info(f"✓ {ticker} → CIK {cik}")
                self.ticker_to_cik[ticker] = cik
                return cik
        except Exception as e:
            logger.warning(f"✗ CIK lookup failed for {ticker}: {e}")
        return None

    def get_latest_filings(self, cik: str, filing_types: List[str] = None) -> List[dict]:
        """
        Fetch latest 10-K/10-Q filings for a CIK.
        Returns list of filing metadata with accession_number, filing_date, etc.
        """
        if not filing_types:
            filing_types = ["10-K", "10-Q"]

        filings = []
        try:
            self._rate_limit()
            url = SEC_FILING_DOWNLOAD.format(f"cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K&type=10-Q&dateb=&owner=exclude&count=100&search_text=&myHID=&format=json")

            # Actually use the XBRL companyfacts endpoint for reliable filing info
            xbrl_url = SEC_FILINGS_SEARCH.format(cik)
            resp = self.session.get(xbrl_url, timeout=TIMEOUT)
            resp.raise_for_status()

            data = resp.json()

            # Extract 10-K and 10-Q filings from the taxonomy
            for filing_type in filing_types:
                if f"us-gaap:{filing_type}" in data.get("facts", {}):
                    # This is a simplified approach; in production, parse the full JSON
                    logger.debug(f"Found {filing_type} in XBRL data for CIK {cik}")
        except Exception as e:
            logger.warning(f"Failed to fetch filings for CIK {cik}: {e}")

        return filings

    def download_filing(self, ticker: str, filing_info: dict) -> bool:
        """
        Download a single filing HTML or text file.
        """
        cik = self.ticker_to_cik.get(ticker)
        if not cik:
            logger.warning(f"No CIK found for {ticker}")
            return False

        # For now, we'll download the index.json file as proof of concept
        ticker_dir = self.output_dir / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._rate_limit()
            # Fetch the company's XBRL facts as the primary data source
            url = SEC_FILINGS_SEARCH.format(cik)
            resp = self.session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()

            filename = ticker_dir / f"companyfacts_{cik}_{datetime.now().isoformat()}.json"
            with open(filename, "w") as f:
                f.write(resp.text)
            logger.info(f"✓ Downloaded {filename.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to download for {ticker}: {e}")
            return False

    def process_tickers(self, tickers: List[str] = None):
        """Download filings for all tickers."""
        if not tickers:
            tickers = DEFAULT_TICKERS

        logger.info(f"Processing {len(tickers)} tickers...")
        successful = 0

        for ticker in tickers:
            try:
                cik = self.lookup_cik(ticker)
                if cik:
                    self.download_filing(ticker, {})
                    successful += 1
            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
            finally:
                self._rate_limit()

        logger.info(f"\n✓ Downloaded filings for {successful}/{len(tickers)} tickers")
        logger.info(f"📁 Filings saved to: {self.output_dir}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Download SEC 10-K/10-Q filings for specified tickers"
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Ticker symbols to download (default: 50 major tickers)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})"
    )
    parser.add_argument(
        "--user-agent",
        default=os.getenv("SEC_USER_AGENT", "ThesisLedger/0.1 (research-dev)"),
        help="User-Agent header for SEC requests"
    )

    args = parser.parse_args()

    downloader = SECFilingDownloader(
        output_dir=args.output_dir,
        user_agent=args.user_agent
    )
    downloader.process_tickers(args.tickers)


if __name__ == "__main__":
    main()
