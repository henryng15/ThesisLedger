"""Seed the company selector with the demo companies used throughout the project."""

from django.core.management.base import BaseCommand

from apps.ledger.models import Company

# Must stay in sync with DEFAULT_TICKERS in scripts/download_filings.py —
# ingest_filings skips any data/raw/{TICKER}/ with no matching Company row.
COMPANIES = [
    {"ticker": "AAPL", "name": "Apple Inc.", "cik": "0000320193"},
    {"ticker": "MSFT", "name": "Microsoft Corporation", "cik": "0000789019"},
    {"ticker": "NVDA", "name": "NVIDIA Corporation", "cik": "0001045810"},
    {"ticker": "JPM", "name": "JPMorgan Chase & Co.", "cik": "0000019617"},
    {"ticker": "V", "name": "Visa Inc.", "cik": "0001403161"},
    {"ticker": "UNH", "name": "UnitedHealth Group Inc.", "cik": "0000731766"},
    {"ticker": "LLY", "name": "Eli Lilly and Company", "cik": "0000059478"},
    {"ticker": "WMT", "name": "Walmart Inc.", "cik": "0000104169"},
    {"ticker": "KO", "name": "The Coca-Cola Company", "cik": "0000021344"},
    {"ticker": "XOM", "name": "Exxon Mobil Corporation", "cik": "0000034088"},
]


class Command(BaseCommand):
    help = "Create or update the supported companies."

    def handle(self, *args, **options) -> None:
        for entry in COMPANIES:
            company, created = Company.objects.update_or_create(
                ticker=entry["ticker"],
                defaults={"name": entry["name"], "cik": entry["cik"], "is_active": True},
            )
            verb = "created" if created else "updated"
            self.stdout.write(f"{verb}: {company}")

        self.stdout.write(self.style.SUCCESS(f"{len(COMPANIES)} companies seeded."))
