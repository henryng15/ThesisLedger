from django.contrib import admin

from apps.ledger.models import AnalysisJob, Chunk, Claim, Company, Evidence, Filing, Thesis


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("ticker", "name", "cik", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("ticker", "name", "cik")


@admin.register(Filing)
class FilingAdmin(admin.ModelAdmin):
    list_display = ("company", "filing_type", "period_end", "filed_at", "ingested_at")
    list_filter = ("filing_type", "company")
    search_fields = ("accession_number",)
    date_hierarchy = "period_end"


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("filing", "ordinal", "section", "token_count", "has_embedding")
    list_filter = ("filing__company", "section")
    search_fields = ("text",)
    # Chunk.text and the 768-dim vector are heavy; keep them out of the list query.
    exclude = ("embedding",)

    @admin.display(boolean=True, description="embedded")
    def has_embedding(self, obj: Chunk) -> bool:
        return obj.embedding is not None


class ClaimInline(admin.TabularInline):
    model = Claim
    extra = 0
    fields = ("ordinal", "text", "origin", "is_approved")


@admin.register(Thesis)
class ThesisAdmin(admin.ModelAdmin):
    list_display = ("company", "short_text", "status", "created_at")
    list_filter = ("status", "company")
    search_fields = ("text",)
    inlines = [ClaimInline]

    @admin.display(description="thesis")
    def short_text(self, obj: Thesis) -> str:
        return obj.text[:80]


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("thesis", "ordinal", "text", "origin", "is_approved")
    list_filter = ("origin", "is_approved")
    search_fields = ("text",)


@admin.register(AnalysisJob)
class AnalysisJobAdmin(admin.ModelAdmin):
    list_display = ("id", "thesis", "status", "progress", "total_claims", "started_at", "finished_at")
    list_filter = ("status",)
    readonly_fields = ("graph_state",)


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ("claim", "status", "similarity", "chunk", "created_at")
    list_filter = ("status",)
    search_fields = ("quote", "explanation")
