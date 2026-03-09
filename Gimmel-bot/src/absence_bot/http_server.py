from __future__ import annotations

import time
from typing import Callable, Optional

from aiohttp import web


class HealthServer:
    def __init__(self, host: str, port: int, version: str, readiness_check: Callable[[], bool]) -> None:
        self._host = host
        self._port = port
        self._version = version
        self._readiness_check = readiness_check
        self._started_at = time.time()
        self._runner: Optional[web.AppRunner] = None

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/healthz", self.healthz)
        app.router.add_get("/readyz", self.readyz)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def healthz(self, _: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "ok",
                "version": self._version,
                "uptime_sec": int(time.time() - self._started_at),
            }
        )

    async def readyz(self, _: web.Request) -> web.Response:
        if self._readiness_check():
            return web.json_response({"status": "ready"}, status=200)
        return web.json_response({"status": "not_ready"}, status=503)
