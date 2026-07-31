"""Seed the company selector with the demo companies used throughout the project."""

from django.core.management.base import BaseCommand

from apps.ledger.models import Company

COMPANIES = [
    {"ticker": "AAPL", "name": "Apple Inc.", "cik": "0000320193"},
    {"ticker": "MSFT", "name": "Microsoft Corporation", "cik": "0000789019"},
    {"ticker": "NVDA", "name": "NVIDIA Corporation", "cik": "0001045810"},
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
