from __future__ import annotations

from pathlib import Path


ONLINE_SMOKE_PATH = Path("hh-applicant-tool/test_script.py")


def pytest_addoption(parser):
    parser.addoption(
        "--run-online-smoke",
        action="store_true",
        default=False,
        help="Run external online smoke tests (requires network access).",
    )


def pytest_ignore_collect(collection_path, config) -> bool:
    if config.getoption("--run-online-smoke"):
        return False

    path = Path(str(collection_path))
    try:
        rel_path = path.relative_to(Path.cwd())
    except ValueError:
        return False

    return rel_path == ONLINE_SMOKE_PATH
