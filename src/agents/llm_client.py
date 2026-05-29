from __future__ import annotations

import json
import re

from openai import OpenAI

from src.config import get_settings

JSON_ONLY_INSTRUCTION = (
    "Return JSON only. Do not include markdown fences. Do not include explanation."
)


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
            resp = self._client.chat.completions.create(
                model=self.model, messages=messages, temperature=0
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            print(f"[warning] LLM chat failed: {exc}")
            return ""

    def _with_json_only_instruction(self, messages: list[dict]) -> list[dict]:
        prepared = [dict(message) for message in messages]
        for message in prepared:
            if message.get("role") == "system":
                content = str(message.get("content") or "").strip()
                if JSON_ONLY_INSTRUCTION not in content:
                    message["content"] = (
                        f"{content}\n{JSON_ONLY_INSTRUCTION}"
                        if content
                        else JSON_ONLY_INSTRUCTION
                    )
                return prepared
        return [{"role": "system", "content": JSON_ONLY_INSTRUCTION}, *prepared]

    def _clean_json_response(self, response: str) -> str:
        cleaned = (response or "").strip()
        if not cleaned:
            return ""

        json_block = re.search(
            r"```json\s*(.*?)\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL
        )
        if json_block:
            cleaned = json_block.group(1).strip()
        else:
            code_block = re.search(r"```\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
            if code_block:
                cleaned = code_block.group(1).strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and start <= end:
            cleaned = cleaned[start : end + 1].strip()
        return cleaned

    def chat_json(self, messages: list[dict], fallback: dict | None = None) -> dict:
        fb = fallback or {}
        if not self.is_enabled():
            return fb
        raw = self.chat(self._with_json_only_instruction(messages))
        cleaned = self._clean_json_response(raw)
        if not cleaned:
            return fb
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
            print(
                "[warning] LLM JSON parse failed: decoded JSON is not an object; "
                f"response={raw[:300]!r}"
            )
            return fb
        except Exception as exc:  # noqa: BLE001
            print(f"[warning] LLM JSON parse failed: {exc}; response={raw[:300]!r}")
            return fb
