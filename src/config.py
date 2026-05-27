"""Project configuration loading utilities."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application settings loaded from YAML + environment variables."""

    project_name: str
    duckdb_path: str
    trademark_raw_dir: str
    trademark_sample_dir: str
    platform_raw_dir: str
    platform_sample_dir: str
    patent_claims_raw_dir: str
    patent_claims_sample_dir: str
    litigation_raw_dir: str
    litigation_sample_dir: str
    chroma_platform_dir: str
    chroma_claims_dir: str
    bm25_platform_path: str
    bm25_claims_path: str
    embedding_model_name: str
    top_k: int = 10
    rerank_top_k: int = 5
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""
    mock_llm: bool = Field(default=False)


def _to_bool(value: Any, default: bool = False) -> bool:
    """Convert a value into bool with safe defaults."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _read_yaml_config(path: Path) -> dict[str, Any]:
    """Read default YAML config into a plain dictionary."""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config at {path}: root must be a mapping.")
    return data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings from ``configs/default.yaml`` and ``.env``.

    Precedence:
    1) Environment variables in current environment or `.env`
    2) Values from YAML defaults
    """

    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", override=False)

    defaults = _read_yaml_config(root / "configs" / "default.yaml")

    openai_api_key = __import__("os").environ.get("OPENAI_API_KEY", "")
    openai_base_url = __import__("os").environ.get("OPENAI_BASE_URL", "")
    openai_model = __import__("os").environ.get("OPENAI_MODEL", "")
    env_mock = __import__("os").environ.get("MOCK_LLM")

    mock_llm_default = _to_bool(defaults.get("mock_llm", False), default=False)
    mock_llm = _to_bool(env_mock, default=mock_llm_default)

    payload: dict[str, Any] = {
        "project_name": defaults.get("project_name", "CrossBorder Marketplace RAG Agent"),
        "duckdb_path": defaults["duckdb_path"],
        "trademark_raw_dir": defaults["trademark_raw_dir"],
        "trademark_sample_dir": defaults["trademark_sample_dir"],
        "platform_raw_dir": defaults["platform_raw_dir"],
        "platform_sample_dir": defaults["platform_sample_dir"],
        "patent_claims_raw_dir": defaults["patent_claims_raw_dir"],
        "patent_claims_sample_dir": defaults["patent_claims_sample_dir"],
        "litigation_raw_dir": defaults["litigation_raw_dir"],
        "litigation_sample_dir": defaults["litigation_sample_dir"],
        "chroma_platform_dir": defaults["chroma_platform_dir"],
        "chroma_claims_dir": defaults["chroma_claims_dir"],
        "bm25_platform_path": defaults["bm25_platform_path"],
        "bm25_claims_path": defaults["bm25_claims_path"],
        "embedding_model_name": defaults["embedding_model_name"],
        "top_k": int(defaults.get("top_k", 10)),
        "rerank_top_k": int(defaults.get("rerank_top_k", 5)),
        "openai_api_key": openai_api_key,
        "openai_base_url": openai_base_url,
        "openai_model": openai_model,
        "mock_llm": mock_llm,
    }
    return Settings(**payload)
