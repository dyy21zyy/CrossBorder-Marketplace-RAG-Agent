from __future__ import annotations

import subprocess
import sys


def test_cli_demo_smoke_mock_llm() -> None:
    cmd = [
        sys.executable,
        "scripts/05_run_demo.py",
        "--title",
        "Phone case compatible with iPhone 15",
        "--description",
        "Magnetic transparent phone case for iPhone 15",
        "--category",
        "phone accessory",
        "--platform",
        "Temu",
        "--has_authorization",
        "false",
        "--enable_patent_check",
        "false",
        "--enable_litigation_check",
        "false",
        "--mock_llm",
        "true",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stderr
    assert "=== Parsed Listing ===" in out.stdout
    assert "=== Final Answer ===" in out.stdout
