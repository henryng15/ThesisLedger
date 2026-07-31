"""Management command to ingest SEC filings from data/raw/.

Reads filing HTML files, cleans them, chunks the text, and creates
Filing and Chunk records in the database.
"""

import re
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.ingestion.cleaner import clean_filing_html, detect_filing_type
from apps.ingestion.pipeline import IngestionError, ingest_filing
from apps.ledger.models import Company, Filing


class Command(BaseCommand):
    help = "Ingest SEC filings from data/raw/{TICKER}/ directories"

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-dir",
            type=str,
            default="data/raw",
            help="Directory containing company folders with filings",
        )
        parser.add_argument(
            "--ticker",
            type=str,
            help="Only ingest filings for specific ticker",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip filings that already exist in database",
        )

    def handle(self, *args, **options):
        data_dir = Path(options["data_dir"])
        if not data_dir.exists():
            raise CommandError(f"Data directory not found: {data_dir}")

        ticker_filter = options.get("ticker")
        skip_existing = options["skip_existing"]

        total_filings = 0
        total_chunks = 0

        for company_dir in sorted(data_dir.iterdir()):
            if not company_dir.is_dir():
                continue

            ticker = company_dir.name.upper()

            if ticker_filter and ticker != ticker_filter.upper():
                continue

            company = Company.objects.filter(ticker=ticker).first()
            if not company:
                self.stdout.write(
                    self.style.WARNING(f"Skipping {ticker}: no matching company in database")
                )
                continue

            filing_count, chunk_count = self._ingest_company(
                company, company_dir, skip_existing
            )
            total_filings += filing_count
            total_chunks += chunk_count

        self.stdout.write(
            self.style.SUCCESS(
                f"Ingested {total_filings} filings with {total_chunks} chunks"
            )
        )

    def _ingest_company(
        self, company: Company, company_dir: Path, skip_existing: bool
    ) -> tuple[int, int]:
        """Ingest all filings for a company."""
        filing_count = 0
        chunk_count = 0

        for filing_path in company_dir.glob("*.htm*"):
            try:
                f_count, c_count = self._ingest_filing(
                    company, filing_path, skip_existing
                )
                filing_count += f_count
                chunk_count += c_count
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error ingesting {filing_path}: {e}")
                )

        if filing_count > 0:
            self.stdout.write(f"  {company.ticker}: {filing_count} filings, {chunk_count} chunks")

        return filing_count, chunk_count

    def _ingest_filing(
        self, company: Company, filing_path: Path, skip_existing: bool
    ) -> tuple[int, int]:
        """Ingest a single filing file."""
        # Extract metadata from filename (e.g., 10k_2024.htm)
        filename = filing_path.stem.lower()
        filing_type, period_year = self._parse_filename(filename)

        # Check for existing filing
        period_end = date(period_year, 12, 31)  # Approximate
        existing = Filing.objects.filter(
            company=company,
            filing_type=filing_type,
            period_end__year=period_year,
        ).first()

        if existing:
            if skip_existing:
                return 0, 0
            # Delete existing to re-ingest
            existing.delete()

        # Read and clean HTML
        html_content = filing_path.read_text(encoding="utf-8", errors="replace")
        raw_text = clean_filing_html(html_content)

        if not raw_text or len(raw_text) < 1000:
            self.stdout.write(
                self.style.WARNING(f"Skipping {filing_path}: insufficient content")
            )
            return 0, 0

        # Detect filing type if not clear from filename
        if not filing_type:
            filing_type = detect_filing_type(raw_text)

        try:
            filing = ingest_filing(
                company,
                filing_type=filing_type,
                period_end=period_end,
                filed_at=period_end,  # Approximate
                accession_number=self._generate_accession(company.cik, period_year),
                source_url=f"file://{filing_path.absolute()}",
                raw_text=raw_text,
            )
        except IngestionError as e:
            self.stdout.write(self.style.WARNING(f"Skipping {filing_path}: {e}"))
            return 0, 0

        return 1, filing.chunks.count()

    def _parse_filename(self, filename: str) -> tuple[str, int]:
        """Extract filing type and year from filename."""
        filing_type = "10-K"
        year = 2024  # Default

        if "10q" in filename:
            filing_type = "10-Q"
        elif "10k" in filename:
            filing_type = "10-K"

        # Look for 4-digit year
        year_match = re.search(r"20\d{2}", filename)
        if year_match:
            year = int(year_match.group())

        return filing_type, year

    def _generate_accession(self, cik: str, year: int) -> str:
        """Generate a unique accession number."""
        import uuid
        short_id = uuid.uuid4().hex[:8]
        return f"{cik.zfill(10)}-{year}-{short_id}"
