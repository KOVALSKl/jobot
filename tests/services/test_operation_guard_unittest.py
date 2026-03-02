from __future__ import annotations

import asyncio
import unittest

from bot.services.concurrency import OperationGuard, OperationInProgressError


class OperationGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocks_duplicate_operation_for_same_user(self) -> None:
        guard = OperationGuard(max_global_heavy_tasks=2)
        started = asyncio.Event()
        release = asyncio.Event()

        async def first_job() -> str:
            started.set()
            await release.wait()
            return "done"

        task = asyncio.create_task(guard.run_exclusive_heavy("apply", 42, first_job))
        await started.wait()

        with self.assertRaises(OperationInProgressError):
            await guard.run_exclusive_heavy("apply", 42, lambda: asyncio.sleep(0))

        release.set()
        self.assertEqual(await task, "done")

    async def test_allows_same_operation_for_different_users(self) -> None:
        guard = OperationGuard(max_global_heavy_tasks=2)

        async def job(value: int) -> int:
            await asyncio.sleep(0.01)
            return value

        results = await asyncio.gather(
            guard.run_exclusive_heavy("reply", 1, lambda: job(1)),
            guard.run_exclusive_heavy("reply", 2, lambda: job(2)),
        )
        self.assertEqual(results, [1, 2])

