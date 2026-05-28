from __future__ import annotations

import json

from openai import OpenAI

from src.config import get_settings


class LLMClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url or None
        self.model = settings.openai_model or "gpt-4o-mini"
        self.mock_llm = settings.mock_llm
        self._client = None
        if self.is_enabled():
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def is_enabled(self) -> bool:
        return (not self.mock_llm) and bool(self.api_key)

    def chat(self, messages: list[dict]) -> str:
        if not self.is_enabled() or self._client is None:
            return ""
        try:
            resp = self._client.chat.completions.create(model=self.model, messages=messages, temperature=0)
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            print(f"[warning] LLM chat failed: {exc}")
            return ""

    def chat_json(self, messages: list[dict], fallback: dict | None = None) -> dict:
        fb = fallback or {}
        if not self.is_enabled():
            return fb
        raw = self.chat(messages)
        if not raw:
            return fb
        try:
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            print(f"[warning] LLM JSON parse failed: {exc}")
            return fb
