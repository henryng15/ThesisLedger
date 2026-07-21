import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_reports_ok_with_pgvector(client):
    response = client.get(reverse("health"))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"]["ok"] is True
    assert body["database"]["pgvector"] is not None
