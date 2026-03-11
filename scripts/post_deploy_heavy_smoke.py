from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from bot.celery_app import celery_app

TERMINAL_STATES = {"SUCCESS", "FAILURE", "REVOKED"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-deploy heavy smoke task")
    parser.add_argument("--timeout", type=float, default=60.0, help="Таймаут ожидания terminal status, сек")
    parser.add_argument("--poll", type=float, default=1.0, help="Интервал опроса статуса, сек")
    parser.add_argument(
        "--artifact-path",
        default="artifacts/deploy/post_deploy_heavy_smoke.json",
        help="Путь к JSON-артефакту smoke",
    )
    args = parser.parse_args()

    started = time.monotonic()
    async_result = celery_app.send_task("bot.post_deploy_heavy_smoke")
    final_state = async_result.state
    final_result: str | None = None

    while (time.monotonic() - started) < args.timeout:
        async_result = celery_app.AsyncResult(async_result.id)
        final_state = async_result.state
        if final_state in TERMINAL_STATES:
            result_payload = async_result.result
            final_result = str(result_payload) if result_payload is not None else None
            break
        time.sleep(args.poll)

    duration_ms = round((time.monotonic() - started) * 1000, 2)
    report = {
        "task_id": async_result.id,
        "status": final_state,
        "duration_ms": duration_ms,
        "result": final_result,
    }

    artifact_path = Path(args.artifact_path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False))
    if final_state != "SUCCESS":
        print(
            f"post-deploy smoke failed: task_id={async_result.id} status={final_state}",
            flush=True,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
