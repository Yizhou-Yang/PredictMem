"""Minimal OpenAI-compatible client (works with any /v1 endpoint)."""

from __future__ import annotations

import os
from dataclasses import dataclass



@dataclass
class LLMConfig:
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.0
    timeout: float = 120.0

    @classmethod
    def from_env(cls, model: str | None = None) -> "LLMConfig":
        return cls(
            model=model or os.environ.get("PREDICTMEM_MODEL", "gpt-4o-mini"),
            api_key=os.environ.get("PREDICTMEM_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("PREDICTMEM_BASE_URL") or os.environ.get("OPENAI_BASE_URL"),
        )


class LLMClient:
    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig.from_env()
        from openai import OpenAI

        self._client = OpenAI(
            api_key=self.config.api_key or "EMPTY",
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

    def generate(self, prompt: str, max_tokens: int = 256) -> str:
        response = self._client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()
