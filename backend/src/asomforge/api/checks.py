# 提供配置检查的共享事件流，并在连接断开时取消检查。
import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import suppress

import anyio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from asomforge.api.configurations import require_kind
from asomforge.runtimes.checks import CheckService


def check_stream(request: Request, run: Callable[[], Awaitable[dict]]) -> StreamingResponse:
    async def events():
        task = asyncio.create_task(run())
        try:
            yield 'data: {"status":"running","message":"正在连接并检查配置…"}\n\n'
            while not task.done():
                if await request.is_disconnected():
                    return
                await asyncio.wait({task}, timeout=0.2)
            yield "data: " + json.dumps(await task, ensure_ascii=False) + "\n\n"
        finally:
            with anyio.CancelScope(shield=True):
                if not task.done():
                    task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def check_router(checks: CheckService) -> APIRouter:
    router = APIRouter(prefix="/api/configurations")

    @router.post("/{kind}/{resource_id}/check")
    async def check(kind: str, resource_id: str, request: Request):
        resource = checks.service.repository.get(require_kind(kind), resource_id)
        return check_stream(request, lambda: checks.run(resource))

    return router
