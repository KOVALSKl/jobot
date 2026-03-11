from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from importlib.util import find_spec
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_BACKENDS = REPO_ROOT / "scripts" / "check_installed_backends.py"
IMPORT_SMOKE = REPO_ROOT / "scripts" / "import_smoke_storage.py"
HH_PACKAGE_DIR = REPO_ROOT / "hh-applicant-tool"


def _run_cmd(args: list[str], expect_code: int, label: str) -> tuple[int, str]:
    print(f"[scenario] RUN {label}: {' '.join(args)}")
    proc = subprocess.run(
        args,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    output = (
        f"$ {' '.join(args)}\n"
        f"[exit_code] {proc.returncode}\n"
        f"[stdout]\n{proc.stdout}\n"
        f"[stderr]\n{proc.stderr}\n"
    )
    if proc.returncode != expect_code:
        print(f"[scenario] FAIL {label}: expected exit {expect_code}, got {proc.returncode}")
        print(output)
        raise RuntimeError(f"{label} failed")
    print(f"[scenario] OK {label}: exit={proc.returncode}")
    return proc.returncode, output


def _resolve_backends_file() -> Path:
    spec = find_spec("hh_applicant_tool.backends")
    if spec is None or spec.origin is None:
        raise RuntimeError("Cannot locate installed module 'hh_applicant_tool.backends'")
    path = Path(spec.origin).resolve()
    if "site-packages" not in str(path):
        raise RuntimeError(
            f"Module does not resolve from site-packages: {path}. "
            "Run this script in the target virtualenv with installed package."
        )
    return path


def main() -> int:
    logs_dir = REPO_ROOT / "artifacts" / "stale-scenario"
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    log_file = logs_dir / f"stale_recovery_{timestamp}.log"

    print(f"[scenario] python: {sys.executable}")
    print(f"[scenario] repo: {REPO_ROOT}")
    print(f"[scenario] log file: {log_file}")

    backends_file = _resolve_backends_file()
    print(f"[scenario] installed backends path: {backends_file}")

    backup_dir = Path(tempfile.mkdtemp(prefix="hh_backends_backup_"))
    backup_file = backup_dir / backends_file.name
    shutil.copy2(backends_file, backup_file)

    logs: list[str] = []
    try:
        backends_file.unlink()
        print(f"[scenario] stale state prepared: removed {backends_file}")

        _, output = _run_cmd(
            [sys.executable, str(CHECK_BACKENDS)],
            expect_code=1,
            label="negative-check_installed_backends",
        )
        logs.append(output)

        _, output = _run_cmd(
            [sys.executable, str(IMPORT_SMOKE)],
            expect_code=1,
            label="negative-import_smoke_storage",
        )
        logs.append(output)

        _, output = _run_cmd(
            [sys.executable, "-m", "pip", "install", "--force-reinstall", str(HH_PACKAGE_DIR)],
            expect_code=0,
            label="reinstall-hh-applicant-tool",
        )
        logs.append(output)

        _, output = _run_cmd(
            [sys.executable, str(CHECK_BACKENDS)],
            expect_code=0,
            label="recovery-check_installed_backends",
        )
        logs.append(output)

        _, output = _run_cmd(
            [sys.executable, str(IMPORT_SMOKE)],
            expect_code=0,
            label="recovery-import_smoke_storage",
        )
        logs.append(output)
    finally:
        if not backends_file.exists() and backup_file.exists():
            shutil.copy2(backup_file, backends_file)
        shutil.rmtree(backup_dir, ignore_errors=True)

    log_file.write_text("\n".join(logs), encoding="utf-8")
    print("[scenario] PASS: negative and recovery scenario completed")
    print(f"[scenario] evidence saved to {log_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
