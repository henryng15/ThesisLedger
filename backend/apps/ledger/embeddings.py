"""Embedding helpers for the retrieval layer."""

from __future__ import annotations

import os
from typing import Any

import requests
from django.conf import settings


class EmbeddingServiceError(RuntimeError):
    """Raised when an embedding request cannot be completed."""


class EmbeddingService:
    """Small Ollama wrapper for generating embeddings."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or getattr(settings, "OLLAMA_BASE_URL", None) or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self.model = model or getattr(settings, "OLLAMA_EMBED_MODEL", None) or os.getenv("OLLAMA_EMBED_MODEL") or "nomic-embed-text"

    def embed_text(self, text: str) -> list[float]:
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=20,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise EmbeddingServiceError(f"Embedding request failed: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise EmbeddingServiceError("Embedding response was not valid JSON.") from exc

        embedding = payload.get("embedding")
        if not isinstance(embedding, list):
            raise EmbeddingServiceError("Embedding payload did not contain a list of floats.")
        return [float(value) for value in embedding]


def build_embedding_service() -> EmbeddingService:
    return EmbeddingService()
