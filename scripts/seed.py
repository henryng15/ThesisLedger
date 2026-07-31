#!/usr/bin/env python
"""One-command database seeding for ThesisLedger.

Seeds companies, ingests filings from data/raw/, and optionally
generates embeddings. Run from project root or backend directory.

Usage:
    python scripts/seed.py [--skip-embed] [--ticker TICKER]
"""

import argparse
import os
import sys
from pathlib import Path

# Setup Django
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
backend_dir = project_root / "backend"

sys.path.insert(0, str(backend_dir))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.core.management import call_command


def main():
    parser = argparse.ArgumentParser(description="Seed ThesisLedger database")
    parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="Skip embedding generation (faster, but search won't work)",
    )
    parser.add_argument(
        "--ticker",
        type=str,
        help="Only seed specific ticker (e.g., AAPL)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/raw",
        help="Directory containing SEC filings",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("ThesisLedger Database Seeder")
    print("=" * 60)

    # Step 1: Run migrations
    print("\n[1/4] Running migrations...")
    call_command("migrate", verbosity=1)

    # Step 2: Seed companies
    print("\n[2/4] Seeding companies...")
    call_command("seed_companies")

    # Step 3: Ingest filings
    print("\n[3/4] Ingesting SEC filings...")
    ingest_args = ["--data-dir", args.data_dir, "--skip-existing"]
    if args.ticker:
        ingest_args.extend(["--ticker", args.ticker])

    try:
        call_command("ingest_filings", *ingest_args)
    except Exception as e:
        print(f"  Warning: Ingest failed or no filings found: {e}")
        print("  (This is OK if data/raw/ is empty - C will download filings)")

    # Step 4: Generate embeddings
    if not args.skip_embed:
        print("\n[4/4] Generating embeddings...")
        try:
            from apps.ingestion.embeddings import embed_all_chunks, check_ollama_connection

            if check_ollama_connection():
                count = embed_all_chunks()
                print(f"  Embedded {count} chunks")
            else:
                print("  Skipping: Ollama not available")
                print("  Run later: python -c 'from apps.ingestion.embeddings import embed_all_chunks; embed_all_chunks()'")

        except Exception as e:
            print(f"  Warning: Embedding failed: {e}")
            print("  Run later when Ollama is available")
    else:
        print("\n[4/4] Skipping embeddings (--skip-embed)")

    print("\n" + "=" * 60)
    print("Seeding complete!")
    print("=" * 60)

    # Print summary
    from apps.ledger.models import Company, Filing, Chunk
    print(f"\nDatabase summary:")
    print(f"  Companies: {Company.objects.count()}")
    print(f"  Filings:   {Filing.objects.count()}")
    print(f"  Chunks:    {Chunk.objects.count()}")
    print(f"  Embedded:  {Chunk.objects.exclude(embedding__isnull=True).count()}")


if __name__ == "__main__":
    main()
