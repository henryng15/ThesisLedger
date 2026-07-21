"""Hard-coded payloads for the Day 2 stub API.

Every shape here comes straight from docs/api_contract.md. Ids are fixed so the
frontend can hard-code them while the real persistence lands (Day 3–4).
Delete this module once every endpoint reads from the database.
"""

STUB_THESIS_ID = "11111111-1111-4111-8111-111111111111"
STUB_JOB_ID = "22222222-2222-4222-8222-222222222222"
STUB_CLAIM_IDS = [
    "33333333-3333-4333-8333-333333333331",
    "33333333-3333-4333-8333-333333333332",
    "33333333-3333-4333-8333-333333333333",
]

STUB_THESIS_TEXT = (
    "Apple's services segment keeps growing faster than hardware, and margins "
    "expand as the installed base monetizes."
)

STUB_CLAIMS = [
    {
        "id": STUB_CLAIM_IDS[0],
        "ordinal": 0,
        "text": "Services revenue grows faster than product revenue.",
        "origin": "llm",
        "is_approved": False,
    },
    {
        "id": STUB_CLAIM_IDS[1],
        "ordinal": 1,
        "text": "Gross margin expands as the services mix increases.",
        "origin": "llm",
        "is_approved": False,
    },
    {
        "id": STUB_CLAIM_IDS[2],
        "ordinal": 2,
        "text": "The installed base of active devices keeps growing.",
        "origin": "llm",
        "is_approved": False,
    },
]

STUB_SOURCE = {
    "chunk_id": "44444444-4444-4444-8444-444444444444",
    "section": "Item 7. Management's Discussion and Analysis",
    "filing_type": "10-K",
    "period_end": "2024-09-28",
    "filed_at": "2024-11-01",
    "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm",
}

STUB_RESULTS = [
    {
        "claim": {k: STUB_CLAIMS[0][k] for k in ("id", "ordinal", "text")},
        "evidence": {
            "id": "55555555-5555-4555-8555-555555555551",
            "status": "supported",
            "explanation": (
                "The filing reports services net sales up 13% year over year while "
                "total products grew 2%."
            ),
            "quote": "Services net sales increased 13% during 2024 compared to 2023.",
            "similarity": 0.83,
            "source": STUB_SOURCE,
        },
    },
    {
        "claim": {k: STUB_CLAIMS[1][k] for k in ("id", "ordinal", "text")},
        "evidence": {
            "id": "55555555-5555-4555-8555-555555555552",
            "status": "contradicted",
            "explanation": (
                "Total gross margin percentage was flat year over year despite the "
                "richer services mix."
            ),
            "quote": "Total gross margin percentage was 46.2% in 2024 compared to 44.1% in 2023.",
            "similarity": 0.71,
            "source": STUB_SOURCE,
        },
    },
    {
        "claim": {k: STUB_CLAIMS[2][k] for k in ("id", "ordinal", "text")},
        "evidence": {
            "id": "55555555-5555-4555-8555-555555555553",
            "status": "insufficient_evidence",
            "explanation": "No retrieved passage states the size or growth of the installed base.",
            "quote": "",
            "similarity": None,
            "source": None,
        },
    },
]

STUB_JOB = {
    "id": STUB_JOB_ID,
    "thesis_id": STUB_THESIS_ID,
    "status": "done",
    "progress": 3,
    "total_claims": 3,
    "error": None,
    "started_at": "2026-07-21T20:00:01Z",
    "finished_at": "2026-07-21T20:00:09Z",
    "results": STUB_RESULTS,
}
