from __future__ import annotations

from typing import Any

from src.agents.llm_client import JSON_ONLY_INSTRUCTION, LLMClient


def _client_returning(
    response: str, captured: list[list[dict[str, Any]]] | None = None
) -> LLMClient:
    client = object.__new__(LLMClient)
    client.mock_llm = False

    def is_enabled() -> bool:
        return True

    def chat(messages: list[dict[str, Any]]) -> str:
        if captured is not None:
            captured.append(messages)
        return response

    client.is_enabled = is_enabled  # type: ignore[method-assign]
    client.chat = chat  # type: ignore[method-assign]
    return client


def test_llm_client_mock_or_no_key_returns_fallback() -> None:
    client = LLMClient()
    out = client.chat_json([{"role": "user", "content": "hi"}], fallback={"ok": True})
    assert isinstance(out, dict)
    if not client.is_enabled():
        assert out == {"ok": True}


def test_chat_json_parses_plain_json() -> None:
    client = _client_returning('{"ok": true, "score": 5}')

    assert client.chat_json(
        [{"role": "user", "content": "hi"}], fallback={"ok": False}
    ) == {
        "ok": True,
        "score": 5,
    }


def test_chat_json_adds_strict_json_system_instruction() -> None:
    captured: list[list[dict[str, Any]]] = []
    client = _client_returning('{"ok": true}', captured)

    assert client.chat_json([{"role": "user", "content": "hi"}], fallback={}) == {
        "ok": True
    }
    assert captured[0][0] == {"role": "system", "content": JSON_ONLY_INSTRUCTION}


def test_chat_json_parses_json_markdown_fence() -> None:
    client = _client_returning('```json\n{"ok": true}\n```')

    assert client.chat_json(
        [{"role": "user", "content": "hi"}], fallback={"ok": False}
    ) == {"ok": True}


def test_chat_json_parses_plain_markdown_fence() -> None:
    client = _client_returning('```\n{"ok": true}\n```')

    assert client.chat_json(
        [{"role": "user", "content": "hi"}], fallback={"ok": False}
    ) == {"ok": True}


def test_chat_json_parses_json_with_surrounding_explanation() -> None:
    client = _client_returning('Here is the result:\n{"ok": true}\nHope this helps.')

    assert client.chat_json(
        [{"role": "user", "content": "hi"}], fallback={"ok": False}
    ) == {"ok": True}


def test_chat_json_returns_fallback_for_empty_response() -> None:
    fallback = {"ok": False, "reason": "fallback"}
    client = _client_returning("   ")

    assert (
        client.chat_json([{"role": "user", "content": "hi"}], fallback=fallback)
        == fallback
    )


def test_chat_json_returns_fallback_for_non_json_text(capsys: Any) -> None:
    fallback = {"ok": False, "reason": "fallback"}
    client = _client_returning("API error: quota exceeded")

    assert (
        client.chat_json([{"role": "user", "content": "hi"}], fallback=fallback)
        == fallback
    )
    captured = capsys.readouterr()
    assert "[warning] LLM JSON parse failed" in captured.out
    assert "API error: quota exceeded" in captured.out
