from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response


def _database_status() -> dict[str, object]:
    """Report DB reachability plus whether the pgvector extension is installed."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            row = cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - health endpoint reports, never raises
        return {"ok": False, "error": str(exc), "pgvector": None}
    return {"ok": True, "error": None, "pgvector": row[0] if row else None}


@api_view(["GET"])
def health(request: Request) -> Response:
    """Liveness + dependency check used by Docker healthchecks and kind probes."""
    database = _database_status()
    payload = {
        "status": "ok" if database["ok"] and database["pgvector"] else "degraded",
        "service": "thesisledger-api",
        "version": "0.1.0",
        "database": database,
    }
    return Response(payload, status=200 if payload["status"] == "ok" else 503)
