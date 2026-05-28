"""Load Temu platform IP policy PDF by page."""

from __future__ import annotations

from pathlib import Path

import fitz

from src.config import get_settings


class PlatformPolicyFileNotFoundError(FileNotFoundError):
    """Raised when neither raw nor sample Temu policy file exists."""


def resolve_platform_policy_path() -> Path:
    """Resolve Temu policy path, preferring raw dir and falling back to sample dir."""
    settings = get_settings()
    raw_path = Path(settings.platform_raw_dir) / "temu_ip_policy.pdf"
    sample_path = Path(settings.platform_sample_dir) / "temu_ip_policy.pdf"

    if raw_path.exists():
        return raw_path
    if sample_path.exists():
        return sample_path

    raise PlatformPolicyFileNotFoundError(
        "Temu IP Policy PDF not found. Checked paths: "
        f"{raw_path} (preferred), {sample_path} (fallback)."
    )


def load_platform_policy_pages(pdf_path: str | Path | None = None) -> list[dict[str, str | int]]:
    """Read PDF with PyMuPDF and return page-level text records.

    Returns a list like: [{"page_number": 1, "text": "..."}, ...].
    """
    path = Path(pdf_path) if pdf_path else resolve_platform_policy_path()
    if not path.exists():
        raise PlatformPolicyFileNotFoundError(f"Temu IP Policy PDF not found: {path}")

    pages: list[dict[str, str | int]] = []
    with fitz.open(path) as doc:
        for idx, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            pages.append({"page_number": idx, "text": text})
    return pages
