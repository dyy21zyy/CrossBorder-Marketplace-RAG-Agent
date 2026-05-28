from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    app_path = Path("src/webapp/app.py")
    print("Run: streamlit run src/webapp/app.py")
    if not app_path.exists():
        raise FileNotFoundError(f"Missing app file: {app_path}")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=False)


if __name__ == "__main__":
    main()
