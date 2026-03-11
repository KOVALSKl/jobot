from __future__ import annotations

import importlib
import os
import sys
from importlib.util import find_spec
from pathlib import Path


def _is_from_repo(path: Path, repo_root: Path) -> bool:
    try:
        path.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        return False


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    source_tree_root = repo_root / "hh-applicant-tool" / "src"
    print(f"[sanity] repo root: {repo_root}")
    print(f"[sanity] python executable: {sys.executable}")
    print(f"[sanity] PYTHONPATH={os.environ.get('PYTHONPATH', '')!r}")

    spec = find_spec("hh_applicant_tool.backends")
    if spec is None or spec.origin is None:
        print("[sanity] FAIL: module 'hh_applicant_tool.backends' is not importable")
        return 1

    module_path = Path(spec.origin).resolve()
    print(f"[sanity] hh_applicant_tool.backends path: {module_path}")
    if "site-packages" not in str(module_path):
        print(
            "[sanity] FAIL: module is not from site-packages, installation looks stale"
        )
        return 1
    if _is_from_repo(module_path, source_tree_root):
        print(
            "[sanity] FAIL: module resolved from hh-applicant-tool/src, expected site-packages"
        )
        return 1

    package = importlib.import_module("hh_applicant_tool")
    package_path = Path(getattr(package, "__file__", "")).resolve()
    print(f"[sanity] hh_applicant_tool package path: {package_path}")
    print("[sanity] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
