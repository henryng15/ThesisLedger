"""Thin LLM adapter for claim generation and future retrieval work."""

from __future__ import annotations

import os
from typing import Any

import requests
from django.conf import settings


class LLMServiceError(RuntimeError):
    """Raised when the configured LLM provider cannot produce a response."""


class LLMService:
    """Simple provider-agnostic LLM wrapper with an Ollama-first default."""

    def __init__(self, provider: str | None = None, base_url: str | None = None) -> None:
        self.provider = (provider or os.getenv("LLM_PROVIDER") or "ollama").strip().lower()
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_LLM_MODEL") or "llama3.2:3b"
        self.groq_model = os.getenv("GROQ_MODEL") or "llama-3.1-8b-instant"
        self.openrouter_model = os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini"

    def _build_prompt(self, thesis_text: str) -> str:
        return (
            "You are extracting concise, testable investment thesis claims. "
            "Return JSON with a single key 'claims' whose value is an array of strings. "
            f"Do not add commentary. Thesis: {thesis_text}"
        )

    def _parse_response(self, payload: dict[str, Any]) -> list[str]:
        if isinstance(payload, dict) and isinstance(payload.get("claims"), list):
            claims = [str(item).strip() for item in payload["claims"] if str(item).strip()]
            return claims

        text = payload.get("response") if isinstance(payload, dict) else None
        if isinstance(text, str) and text.strip():
            return [line.strip() for line in text.splitlines() if line.strip()]

        raise LLMServiceError("The provider returned an unexpected payload shape.")

    def _request_json(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LLMServiceError(f"LLM request failed: {exc}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise LLMServiceError("The provider returned invalid JSON.") from exc

    def generate_claims(self, thesis_text: str, max_claims: int = 3) -> list[str]:
        if self.provider == "ollama":
            data = self._request_json(
                url=f"{self.base_url}/api/generate",
                headers={},
                payload={
                    "model": self.model,
                    "prompt": self._build_prompt(thesis_text),
                    "stream": False,
                    "format": "json",
                },
            )
        elif self.provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise LLMServiceError("GROQ_API_KEY is not configured.")
            data = self._request_json(
                url="https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                payload={
                    "model": self.groq_model,
                    "messages": [{"role": "user", "content": self._build_prompt(thesis_text)}],
                    "temperature": 0.2,
                },
            )
            if isinstance(data.get("choices"), list) and data["choices"]:
                message = data["choices"][0].get("message", {})
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    data = {"response": message["content"]}
                else:
                    raise LLMServiceError("GROQ did not return a usable chat response.")
        elif self.provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise LLMServiceError("OPENROUTER_API_KEY is not configured.")
            data = self._request_json(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com",
                    "X-Title": "ThesisLedger",
                },
                payload={
                    "model": self.openrouter_model,
                    "messages": [{"role": "user", "content": self._build_prompt(thesis_text)}],
                    "temperature": 0.2,
                },
            )
            if isinstance(data.get("choices"), list) and data["choices"]:
                message = data["choices"][0].get("message", {})
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    data = {"response": message["content"]}
                else:
                    raise LLMServiceError("OpenRouter did not return a usable chat response.")
        else:
            raise LLMServiceError(f"Unsupported LLM provider: {self.provider}")

        claims = self._parse_response(data)
        if len(claims) > max_claims:
            claims = claims[:max_claims]
        return claims


def build_llm_service() -> LLMService:
    return LLMService(provider=getattr(settings, "LLM_PROVIDER", None))
