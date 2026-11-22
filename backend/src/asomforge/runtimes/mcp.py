# 通过 MCP SDK 完成握手和能力发现，不调用业务工具。
import os
from contextlib import AsyncExitStack
from datetime import timedelta

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from asomforge.runtimes.processes import launch_arguments


async def check_mcp(config: dict, cwd: str, timeout: float) -> dict:
    async with AsyncExitStack() as stack:
        if config["type"] == "stdio":
            command, *args = launch_arguments(
                [config["command"], *config["args"]], cwd, config["env"]
            )
            errlog = stack.enter_context(open(os.devnull, "w"))
            streams = await stack.enter_async_context(
                stdio_client(
                    StdioServerParameters(
                        command=command,
                        args=args,
                        env=config["env"],
                        cwd=cwd,
                    ),
                    errlog=errlog,
                )
            )
        elif config["type"] == "sse":
            streams = await stack.enter_async_context(
                sse_client(
                    config["url"],
                    headers=config["headers"],
                    timeout=timeout,
                    sse_read_timeout=timeout,
                )
            )
        else:
            client = await stack.enter_async_context(
                httpx.AsyncClient(
                    headers=config["headers"],
                    timeout=timeout,
                )
            )
            streams = await stack.enter_async_context(
                streamable_http_client(
                    config["url"],
                    http_client=client,
                )
            )
        session = await stack.enter_async_context(
            ClientSession(
                streams[0],
                streams[1],
                read_timeout_seconds=timedelta(seconds=timeout),
            )
        )
        initialized = await session.initialize()
        details = {"transport": config["type"], "protocol": initialized.protocolVersion}
        capabilities = initialized.capabilities
        if capabilities.tools:
            details["tools"] = len((await session.list_tools()).tools)
        if capabilities.resources:
            details["resources"] = len((await session.list_resources()).resources)
        if capabilities.prompts:
            details["prompts"] = len((await session.list_prompts()).prompts)
        return {
            "status": "passed",
            "code": "connected",
            "details": details,
            "message": "MCP 握手和能力发现完成，未调用业务工具",
        }
