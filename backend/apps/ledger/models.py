"""Domain models — see docs/data_model.md. Frozen after Day 2."""

import uuid

from django.conf import settings
from django.db import models
from pgvector.django import VectorField


class TimestampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Company(TimestampedModel):
    ticker = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255)
    cik = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["ticker"]
        verbose_name_plural = "companies"

    def __str__(self) -> str:
        return f"{self.ticker} — {self.name}"


class Filing(TimestampedModel):
    class FilingType(models.TextChoices):
        ANNUAL = "10-K", "10-K"
        QUARTERLY = "10-Q", "10-Q"

    company = models.ForeignKey(Company, related_name="filings", on_delete=models.CASCADE)
    filing_type = models.CharField(max_length=10, choices=FilingType.choices, db_index=True)
    period_end = models.DateField()
    filed_at = models.DateField()
    accession_number = models.CharField(max_length=25, unique=True)
    source_url = models.URLField(max_length=500)
    raw_text = models.TextField(blank=True)
    ingested_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-period_end"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "filing_type", "period_end"],
                name="unique_filing_per_period",
            )
        ]

    def __str__(self) -> str:
        return f"{self.company.ticker} {self.filing_type} {self.period_end}"


class Chunk(TimestampedModel):
    """A retrievable passage of a filing plus its embedding.

    The HNSW index on `embedding` lands in a later migration (Day 6), after the
    first bulk embed — building it on an empty table is wasted work.
    """

    filing = models.ForeignKey(Filing, related_name="chunks", on_delete=models.CASCADE)
    ordinal = models.PositiveIntegerField()
    section = models.CharField(max_length=120, blank=True, db_index=True)
    text = models.TextField()
    char_start = models.PositiveIntegerField(default=0)
    char_end = models.PositiveIntegerField(default=0)
    token_count = models.PositiveIntegerField(default=0)
    embedding = VectorField(dimensions=settings.EMBEDDING_DIM, null=True, blank=True)

    class Meta:
        ordering = ["filing", "ordinal"]
        constraints = [
            models.UniqueConstraint(fields=["filing", "ordinal"], name="unique_chunk_ordinal")
        ]

    def __str__(self) -> str:
        return f"{self.filing} #{self.ordinal}"


class Thesis(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CLAIMS_GENERATED = "claims_generated", "Claims generated"
        APPROVED = "approved", "Approved"
        ANALYZED = "analyzed", "Analyzed"

    company = models.ForeignKey(Company, related_name="theses", on_delete=models.PROTECT)
    text = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "theses"

    def __str__(self) -> str:
        return f"{self.company.ticker}: {self.text[:60]}"


class Claim(TimestampedModel):
    class Origin(models.TextChoices):
        LLM = "llm", "LLM"
        USER = "user", "User"

    MAX_PER_THESIS = 5

    thesis = models.ForeignKey(Thesis, related_name="claims", on_delete=models.CASCADE)
    ordinal = models.PositiveIntegerField()
    text = models.TextField()
    origin = models.CharField(max_length=10, choices=Origin.choices, default=Origin.LLM)
    is_approved = models.BooleanField(default=False)

    class Meta:
        ordering = ["thesis", "ordinal"]
        constraints = [
            models.UniqueConstraint(fields=["thesis", "ordinal"], name="unique_claim_ordinal")
        ]

    def __str__(self) -> str:
        return self.text[:80]


class AnalysisJob(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    thesis = models.ForeignKey(Thesis, related_name="jobs", on_delete=models.CASCADE)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    progress = models.PositiveIntegerField(default=0)
    total_claims = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    graph_state = models.JSONField(default=dict, blank=True)
    cache_key = models.CharField(max_length=64, blank=True, db_index=True)
    celery_task_id = models.CharField(max_length=64, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"job {self.id} ({self.status})"


class Evidence(TimestampedModel):
    """One verdict for one claim, grounded in exactly one chunk.

    Invariant (enforced on Day 6): a non-`insufficient_evidence` row must carry a
    chunk whose text contains `quote` verbatim. A failed check downgrades the row
    instead of emitting a fabricated citation.
    """

    class Status(models.TextChoices):
        SUPPORTED = "supported", "Supported"
        CONTRADICTED = "contradicted", "Contradicted"
        INSUFFICIENT = "insufficient_evidence", "Insufficient evidence"

    claim = models.ForeignKey(Claim, related_name="evidence", on_delete=models.CASCADE)
    job = models.ForeignKey(AnalysisJob, related_name="evidence", on_delete=models.CASCADE)
    status = models.CharField(max_length=24, choices=Status.choices, db_index=True)
    explanation = models.TextField(blank=True)
    quote = models.TextField(blank=True)
    chunk = models.ForeignKey(
        Chunk, related_name="evidence", on_delete=models.PROTECT, null=True, blank=True
    )
    similarity = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["claim", "-created_at"]
        verbose_name_plural = "evidence"

    def __str__(self) -> str:
        return f"{self.status} for {self.claim_id}"
