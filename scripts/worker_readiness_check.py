from __future__ import annotations

import argparse
import socket
from urllib.parse import urlparse

from redis import Redis

from bot.celery_app import celery_app


def _check_redis_endpoint(label: str, url: str, timeout_s: float) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"redis", "rediss"}:
        return
    client = Redis.from_url(url, socket_connect_timeout=timeout_s, socket_timeout=timeout_s)
    try:
        pong = client.ping()
    except (OSError, socket.error) as ex:
        raise RuntimeError(f"{label}: не удалось подключиться к Redis endpoint {url}: {ex}") from ex
    if not pong:
        raise RuntimeError(f"{label}: Redis endpoint {url} не ответил PONG")


def _check_worker(timeout_s: float) -> None:
    inspector = celery_app.control.inspect(timeout=timeout_s)
    ping_result = inspector.ping()
    if not ping_result:
        raise RuntimeError("worker readiness: celery inspect ping не вернул активных worker")


def main() -> int:
    parser = argparse.ArgumentParser(description="Celery worker readiness check")
    parser.add_argument("--timeout", type=float, default=10.0, help="Таймаут сетевых проверок, сек")
    args = parser.parse_args()

    _check_redis_endpoint("broker readiness", celery_app.conf.broker_url, args.timeout)
    _check_redis_endpoint("result backend readiness", celery_app.conf.result_backend, args.timeout)
    _check_worker(args.timeout)

    print("worker readiness: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
