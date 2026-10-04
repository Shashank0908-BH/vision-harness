"""Bound Daytona metadata and artifact RPCs without retrying model inference."""

import asyncio

from harbor.environments.base import BaseEnvironment
from harbor.environments.daytona.environment import DaytonaEnvironment


class CohortEnvironment(DaytonaEnvironment):
    async def _bounded(self, operation, call, seconds):
        for attempt in range(1, 4):
            try:
                return await asyncio.wait_for(call(), timeout=seconds)
            except (TimeoutError, ConnectionError):
                self.logger.warning("Infrastructure RPC %s timed out/disconnected (attempt %s/3)", operation, attempt)
                if attempt == 3:
                    raise

    async def _create_process_session_with_retry(self, session_id):
        return await self._bounded("create command session",
            lambda: super(CohortEnvironment, self)._create_process_session_with_retry(session_id), 20)

    async def _get_session_command_with_retry(self, session_id, command_id):
        return await self._bounded("read command status",
            lambda: super(CohortEnvironment, self)._get_session_command_with_retry(session_id, command_id), 20)

    async def _get_session_command_logs_with_retry(self, session_id, command_id):
        return await self._bounded("read completed command logs",
            lambda: super(CohortEnvironment, self)._get_session_command_logs_with_retry(session_id, command_id), 20)

    async def is_dir(self, path, user=None):
        # The shell check is bounded and avoids an unbounded metadata RPC.
        return await asyncio.wait_for(BaseEnvironment.is_dir(self, path, user), 30)

    async def is_file(self, path, user=None):
        return await asyncio.wait_for(BaseEnvironment.is_file(self, path, user), 30)

    async def upload_dir(self, source_dir, target_dir):
        return await self._bounded("upload directory",
            lambda: super(CohortEnvironment, self).upload_dir(source_dir, target_dir), 120)

    async def download_dir(self, source_dir, target_dir):
        return await self._bounded("download directory",
            lambda: super(CohortEnvironment, self).download_dir(source_dir, target_dir), 120)

    async def upload_file(self, source_path, target_path):
        return await self._bounded("upload file",
            lambda: super(CohortEnvironment, self).upload_file(source_path, target_path), 60)

    async def download_file(self, source_path, target_path):
        return await self._bounded("download file",
            lambda: super(CohortEnvironment, self).download_file(source_path, target_path), 60)
