from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    print(f"[import-smoke] python executable: {sys.executable}")
    print(f"[import-smoke] PYTHONPATH={os.environ.get('PYTHONPATH', '')!r}")

    backend_module = importlib.import_module("hh_applicant_tool.backends")
    backend_path = Path(getattr(backend_module, "__file__", "")).resolve()
    print(f"[import-smoke] hh_applicant_tool.backends path: {backend_path}")

    importlib.import_module("bot.storage.filesystem")
    importlib.import_module("bot.storage.postgres")

    print("[import-smoke] PASS: imported bot.storage.filesystem and bot.storage.postgres")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
