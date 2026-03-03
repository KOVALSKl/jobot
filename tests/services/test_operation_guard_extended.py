from __future__ import annotations

import asyncio
import unittest

from bot.services.concurrency import OperationGuard, OperationInProgressError


class OperationGuardExtendedTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocks_different_heavy_operations_for_same_user(self) -> None:
        guard = OperationGuard(max_global_heavy_tasks=2, operation_cooldown_seconds=0)
        started = asyncio.Event()
        release = asyncio.Event()

        async def first_job() -> None:
            started.set()
            await release.wait()

        task = asyncio.create_task(guard.run_exclusive_heavy("apply", 7, first_job))
        await started.wait()

        with self.assertRaises(OperationInProgressError):
            await guard.run_exclusive_heavy("reply", 7, lambda: asyncio.sleep(0))

        release.set()
        await task

    async def test_enforces_cooldown_for_same_operation(self) -> None:
        guard = OperationGuard(max_global_heavy_tasks=2, operation_cooldown_seconds=60)

        await guard.run_exclusive_heavy("apply", 11, lambda: asyncio.sleep(0))
        with self.assertRaises(OperationInProgressError):
            await guard.run_exclusive_heavy("apply", 11, lambda: asyncio.sleep(0))
