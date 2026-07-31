from django.urls import path

from apps.ledger import views

urlpatterns = [
    path("companies/", views.company_list, name="company-list"),
    path("uploads/", views.upload_file, name="upload-file"),
    path("theses/", views.thesis_create, name="thesis-create"),
    path("theses/<uuid:thesis_id>/", views.thesis_detail, name="thesis-detail"),
    path("theses/<uuid:thesis_id>/claims:generate", views.claims_generate, name="claims-generate"),
    path("theses/<uuid:thesis_id>/claims:approve", views.claims_approve, name="claims-approve"),
    path("theses/<uuid:thesis_id>/analyze", views.thesis_analyze, name="thesis-analyze"),
    path("claims/<uuid:claim_id>/", views.claim_detail, name="claim-detail"),
    path("jobs/<uuid:job_id>/", views.job_detail, name="job-detail"),
]
