from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HH_TOOL_SRC = ROOT / "hh-applicant-tool" / "src"

for path in (ROOT, HH_TOOL_SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

