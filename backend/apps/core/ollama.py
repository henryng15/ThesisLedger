"""Shared helpers for talking to the Ollama gateway.

Ollama runs on a separate host from the API, so the gateway in front of it
requires a bearer token. This lives here rather than in settings.py because
Django's settings object only exposes upper-case names — a function defined
there is silently unreachable via `django.conf.settings`.
"""

from django.conf import settings


def ollama_headers() -> dict[str, str]:
    """Auth headers for calls to the Ollama gateway.

    Empty when no token is configured, which is only safe when Ollama is
    reachable on localhost.
    """
    token = getattr(settings, "OLLAMA_TOKEN", "")
    return {"Authorization": f"Bearer {token}"} if token else {}
