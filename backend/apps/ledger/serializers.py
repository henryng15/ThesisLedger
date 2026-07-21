"""Serializers mirroring docs/api_contract.md.

Day 2 keeps them read-only over hard-coded payloads; Day 3 swaps the sources for
real querysets without changing these shapes.
"""

from rest_framework import serializers

from apps.ledger.models import Claim, Company, Evidence, Thesis


class CompanySerializer(serializers.ModelSerializer):
    filing_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Company
        fields = ["id", "ticker", "name", "cik", "filing_count"]


class CompanyBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "ticker", "name"]


class ClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = ["id", "ordinal", "text", "origin", "is_approved"]


class ThesisSerializer(serializers.ModelSerializer):
    company = CompanyBriefSerializer(read_only=True)
    claims = ClaimSerializer(many=True, read_only=True)

    class Meta:
        model = Thesis
        fields = ["id", "company", "text", "status", "claims", "created_at"]


class ThesisCreateSerializer(serializers.Serializer):
    company_id = serializers.UUIDField()
    text = serializers.CharField(max_length=5000, allow_blank=False, trim_whitespace=True)


class ClaimUpdateSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)


class ClaimApproveSerializer(serializers.Serializer):
    claim_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


class EvidenceSourceSerializer(serializers.Serializer):
    chunk_id = serializers.UUIDField()
    section = serializers.CharField()
    filing_type = serializers.CharField()
    period_end = serializers.DateField()
    filed_at = serializers.DateField()
    source_url = serializers.URLField()


class EvidenceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=Evidence.Status.choices)
    explanation = serializers.CharField()
    quote = serializers.CharField(allow_blank=True)
    similarity = serializers.FloatField(allow_null=True)
    source = EvidenceSourceSerializer(allow_null=True)


class ClaimResultSerializer(serializers.Serializer):
    claim = serializers.DictField()
    evidence = EvidenceSerializer()


class JobStatusSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    thesis_id = serializers.UUIDField()
    status = serializers.CharField()
    progress = serializers.IntegerField()
    total_claims = serializers.IntegerField()
    error = serializers.CharField(allow_null=True)
    started_at = serializers.DateTimeField(allow_null=True)
    finished_at = serializers.DateTimeField(allow_null=True)
    results = ClaimResultSerializer(many=True)


class JobAcceptedSerializer(serializers.Serializer):
    job_id = serializers.UUIDField()
    status = serializers.CharField()
    thesis_id = serializers.UUIDField()
    total_claims = serializers.IntegerField()
