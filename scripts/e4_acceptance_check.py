from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
HH_TOOL_SRC = ROOT / "hh-applicant-tool" / "src"
for path in (ROOT, HH_TOOL_SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from bot.services.auth import AuthService
from bot.services.heavy_executor import HeavyOperationExecutor, run_heavy_operation


@dataclass
class PerfStats:
    count: int
    min_ms: float
    p50_ms: float
    p95_ms: float
    max_ms: float
    errors: int


class _FakeStorage:
    async def init(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def get_config_backend(self, user_id: int) -> Any:
        raise NotImplementedError

    def get_cookie_backend(self, user_id: int) -> Any:
        raise NotImplementedError

    def get_work_dir(self, user_id: int) -> Path:
        return ROOT


class _FakeGateway:
    def __init__(self) -> None:
        self.closed = 0

    async def refresh_token_if_needed(self) -> bool:
        await asyncio.sleep(0.003)
        return True

    async def aclose(self) -> None:
        self.closed += 1


async def _fake_apply(self, user_id: int, callback, **kwargs: Any) -> None:
    await asyncio.sleep(0.010)
    await callback(f"apply:{user_id}")


async def _fake_clear(self, user_id: int, callback, **kwargs: Any) -> None:
    await asyncio.sleep(0.009)
    await callback(f"clear:{user_id}")


async def _fake_reply(self, user_id: int, callback, **kwargs: Any) -> None:
    await asyncio.sleep(0.011)
    await callback(f"reply:{user_id}")


async def _fake_update(self, user_id: int) -> str:
    await asyncio.sleep(0.008)
    return f"update:{user_id}"


def _build_stats(values_ms: list[float], errors: int) -> PerfStats:
    if not values_ms:
        return PerfStats(count=0, min_ms=0.0, p50_ms=0.0, p95_ms=0.0, max_ms=0.0, errors=errors)
    data = sorted(values_ms)
    idx_95 = max(0, min(len(data) - 1, int(len(data) * 0.95) - 1))
    return PerfStats(
        count=len(values_ms),
        min_ms=round(data[0], 3),
        p50_ms=round(statistics.median(data), 3),
        p95_ms=round(data[idx_95], 3),
        max_ms=round(data[-1], 3),
        errors=errors,
    )


async def _monitor_loop_lag(duration_s: float | None = None, stop_event: asyncio.Event | None = None) -> list[float]:
    interval = 0.010
    lags_ms: list[float] = []
    started = time.perf_counter()
    next_tick = started + interval

    while True:
        if duration_s is not None and (time.perf_counter() - started) >= duration_s:
            break
        if stop_event is not None and stop_event.is_set():
            break

        await asyncio.sleep(max(0.0, next_tick - time.perf_counter()))
        now = time.perf_counter()
        lag_ms = max(0.0, (now - next_tick) * 1000.0)
        lags_ms.append(lag_ms)
        next_tick += interval

    return lags_ms


async def _run_parity_check(user_id: int, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    progress_direct: list[str] = []
    progress_orchestrated: list[str] = []

    direct_executor = HeavyOperationExecutor(storage=_FakeStorage())
    result_direct = await direct_executor.execute(
        user_id=user_id,
        operation=operation,
        payload=payload,
        report_progress=lambda text: progress_direct.append(text),
        is_cancel_requested=lambda: False,
    )

    result_orchestrated = await run_heavy_operation(
        operation=operation,
        payload={"user_id": user_id, **payload},
        report_progress=lambda text: progress_orchestrated.append(text),
        is_cancel_requested=lambda: False,
    )

    parity_ok = result_direct == result_orchestrated and len(progress_direct) == len(progress_orchestrated)
    return {
        "operation": operation,
        "result_direct": result_direct,
        "result_orchestrated": result_orchestrated,
        "progress_direct": progress_direct,
        "progress_orchestrated": progress_orchestrated,
        "parity_ok": parity_ok,
    }


async def _run_auth_refresh(user_id: int) -> float:
    service = AuthService(storage=_FakeStorage())
    gateway = _FakeGateway()
    service._get_gateway = lambda uid: gateway  # type: ignore[method-assign]
    started = time.perf_counter()
    result = await service.refresh_token(user_id)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    normalized = result.lower()
    if "обнов" not in normalized and "refresh" not in normalized:
        raise RuntimeError(f"Unexpected refresh result: {result}")
    if gateway.closed != 1:
        raise RuntimeError("Gateway was not closed after auth refresh.")
    return elapsed_ms


async def _run_workload(concurrency_users: int) -> dict[str, Any]:
    operations = [
        ("apply", {"search": "python"}),
        ("clear", {"older_than": 7, "blacklist": True}),
        ("reply", {"reply_message": "Спасибо за сообщение"}),
        ("update", {}),
    ]

    heavy_latencies_ms: list[float] = []
    auth_latencies_ms: list[float] = []
    errors: list[str] = []

    async def one_user(user_id: int) -> None:
        for operation, payload in operations:
            started = time.perf_counter()
            try:
                await run_heavy_operation(
                    operation=operation,
                    payload={"user_id": user_id, **payload},
                    report_progress=lambda text: None,
                    is_cancel_requested=lambda: False,
                )
            except Exception as ex:
                errors.append(f"{operation}:{user_id}:{ex}")
            else:
                heavy_latencies_ms.append((time.perf_counter() - started) * 1000.0)

        try:
            auth_ms = await _run_auth_refresh(user_id)
        except Exception as ex:
            errors.append(f"auth_refresh:{user_id}:{ex}")
        else:
            auth_latencies_ms.append(auth_ms)

    await asyncio.gather(*(one_user(1000 + idx) for idx in range(concurrency_users)))
    return {
        "heavy_stats": asdict(_build_stats(heavy_latencies_ms, errors=0)),
        "auth_stats": asdict(_build_stats(auth_latencies_ms, errors=0)),
        "errors": errors,
    }


async def run_acceptance(concurrency_users: int) -> dict[str, Any]:
    with (
        patch("bot.services.heavy_executor.create_storage", side_effect=lambda: _FakeStorage()),
        patch("bot.services.heavy_executor.ApplyService.apply_similar", new=_fake_apply),
        patch("bot.services.heavy_executor.NegotiationService.clear", new=_fake_clear),
        patch("bot.services.heavy_executor.NegotiationService.reply_employers", new=_fake_reply),
        patch("bot.services.heavy_executor.ResumeService.update_resumes", new=_fake_update),
    ):
        parity_results = []
        for operation, payload in [
            ("apply", {"search": "python"}),
            ("clear", {"older_than": 7, "blacklist": True}),
            ("reply", {"reply_message": "ok"}),
            ("update", {}),
        ]:
            parity_results.append(await _run_parity_check(user_id=42, operation=operation, payload=payload))

        baseline_lag_ms = await _monitor_loop_lag(duration_s=1.2)

        stop_event = asyncio.Event()
        lag_task = asyncio.create_task(_monitor_loop_lag(stop_event=stop_event))
        workload = await _run_workload(concurrency_users=concurrency_users)
        stop_event.set()
        under_load_lag_ms = await lag_task

    baseline_stats = asdict(_build_stats(baseline_lag_ms, errors=0))
    load_stats = asdict(_build_stats(under_load_lag_ms, errors=0))
    parity_ok = all(item["parity_ok"] for item in parity_results)
    no_errors = not workload["errors"]
    no_burst_regression = workload["heavy_stats"]["p95_ms"] <= workload["heavy_stats"]["p50_ms"] * 2.5
    no_loop_block_growth = load_stats["p95_ms"] <= baseline_stats["p95_ms"] + 20.0

    verdict = parity_ok and no_errors and no_burst_regression and no_loop_block_growth

    return {
        "profile": {
            "concurrency_users": concurrency_users,
            "rationale": "Инженерный baseline для локального контура: N=10 параллельных пользователей как минимально достаточный smoke-профиль без внешнего стенда.",
        },
        "parity": {
            "scenarios": parity_results,
            "ok": parity_ok,
        },
        "perf": {
            "heavy_operation_latency_ms": workload["heavy_stats"],
            "auth_refresh_latency_ms": workload["auth_stats"],
            "event_loop_lag_baseline_ms": baseline_stats,
            "event_loop_lag_under_load_ms": load_stats,
            "no_burst_regression": no_burst_regression,
            "no_loop_block_growth_vs_baseline": no_loop_block_growth,
        },
        "errors": workload["errors"],
        "verdict": "closed" if verdict else "failed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="E4 parity/e2e/perf acceptance check")
    parser.add_argument("--users", type=int, default=10, help="Parallel user count baseline")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "artifacts" / "e4"),
        help="Directory for report artifacts",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = asyncio.run(run_acceptance(concurrency_users=args.users))
    report_path = output_dir / "e4_acceptance_report.json"
    log_path = output_dir / "e4_acceptance_summary.log"

    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log_path.write_text(
        "\n".join(
            [
                f"verdict={result['verdict']}",
                f"users={result['profile']['concurrency_users']}",
                f"parity_ok={result['parity']['ok']}",
                f"no_burst_regression={result['perf']['no_burst_regression']}",
                f"no_loop_block_growth_vs_baseline={result['perf']['no_loop_block_growth_vs_baseline']}",
                f"errors={len(result['errors'])}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Report: {report_path}")
    print(f"Log: {log_path}")
    print(f"Verdict: {result['verdict']}")
    return 0 if result["verdict"] == "closed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
