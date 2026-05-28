from src.agents.llm_client import LLMClient


def test_llm_client_mock_or_no_key_returns_fallback() -> None:
    client = LLMClient()
    out = client.chat_json([{"role": "user", "content": "hi"}], fallback={"ok": True})
    assert isinstance(out, dict)
    if not client.is_enabled():
        assert out == {"ok": True}
