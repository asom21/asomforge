# 暴露模型目录发现、草稿测试和指定保存版本测试的 HTTP 接口。
import asyncio
from contextlib import suppress

import anyio
from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from asomforge.api.checks import check_stream
from asomforge.application.model_connections import ModelConnectionService
from asomforge.domain.model_connections import (
    ModelDiscoverRequest,
    ModelDiscovery,
    ModelProbeRequest,
    SavedModelProbeRequest,
)


def model_connection_router(models: ModelConnectionService) -> APIRouter:
    router = APIRouter(tags=["model-connections"])

    @router.post("/api/model-connections/discover", response_model=ModelDiscovery)
    async def discover(body: ModelDiscoverRequest, request: Request):
        async def disconnected():
            while True:
                if (await request.receive())["type"] == "http.disconnect":
                    return

        task = asyncio.create_task(models.discover(body))
        monitor = asyncio.create_task(disconnected())
        try:
            completed, _ = await asyncio.wait({task, monitor}, return_when=asyncio.FIRST_COMPLETED)
            if task not in completed:
                return Response(status_code=499)
            return ModelDiscovery(models=await task)
        finally:
            with anyio.CancelScope(shield=True):
                for pending in (task, monitor):
                    if not pending.done():
                        pending.cancel()
                for pending in (task, monitor):
                    with suppress(asyncio.CancelledError):
                        await pending

    @router.post(
        "/api/model-connections/test",
        response_class=StreamingResponse,
        responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
    )
    async def draft_test(body: ModelProbeRequest, request: Request):
        prepared = models.draft(body)
        return check_stream(request, lambda: models.run(*prepared))

    @router.post(
        "/api/configurations/models/{resource_id}/test",
        response_class=StreamingResponse,
        responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
    )
    async def saved_test(resource_id: str, body: SavedModelProbeRequest, request: Request):
        prepared = models.saved(resource_id, body)
        return check_stream(request, lambda: models.run(*prepared))

    return router
