from __future__ import annotations

import re

_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def detect_language(text: str) -> str:
    """Detect whether text contains Chinese characters.

    The first version is intentionally deterministic: any CJK Unified
    Ideograph means Chinese (``zh``); otherwise default to English (``en``).
    """
    return "zh" if _CHINESE_RE.search(text or "") else "en"
