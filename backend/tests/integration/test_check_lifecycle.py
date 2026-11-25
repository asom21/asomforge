# 验证超时和连接断开后，MCP 检查能够释放子进程。
import asyncio
import socket
import sys
import time
from contextlib import suppress
from threading import Thread

import httpx
import psutil
import pytest
import uvicorn

from asomforge.domain.configurations import Draft
from asomforge.main import create_app
from asomforge.runtimes.checks import CheckService


def hanging_resource(app, tmp_path):
    script = tmp_path / "hanging.py"
    script.write_text(
        "import os,time,pathlib\n"
        "pathlib.Path(__file__).with_name('pid').write_text(str(os.getpid()))\n"
        "time.sleep(90)\n"
    )
    return app.state.service.save(
        "mcp",
        Draft(
            name="hanging",
            config={
                "command": sys.executable,
                "args": [str(script)],
            },
        ),
    )


@pytest.mark.asyncio
async def test_mcp_timeout_closes_sdk_process(tmp_path):
    from asomforge.runtimes.mcp import check_mcp

    app = create_app(tmp_path)
    resource = hanging_resource(app, tmp_path)
    config = app.state.service.resolved(resource)
    loop = asyncio.get_running_loop()
    timeout_ready = loop.create_future()

    async def check_with_deadline():
        async with asyncio.timeout(None) as deadline:
            timeout_ready.set_result(deadline)
            return await check_mcp(config, str(tmp_path), 30)

    task = asyncio.create_task(check_with_deadline())
    try:
        deadline = await timeout_ready
        # Startup is a precondition: only measure timeout cleanup once the PID is known.
        async with asyncio.timeout(10):
            while not (tmp_path / "pid").exists():
                if task.done():
                    await task
                    pytest.fail("MCP check ended before the child reported its PID")
                await asyncio.sleep(0.02)
        pid = int((tmp_path / "pid").read_text())
        deadline.reschedule(loop.time() + 0.1)
        with pytest.raises(TimeoutError):
            await task
        # Windows may report a terminating process briefly after the SDK closes its handle.
        async with asyncio.timeout(7):
            while psutil.pid_exists(pid):
                await asyncio.sleep(0.02)
        assert not psutil.pid_exists(pid)
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


@pytest.mark.asyncio
async def test_mcp_service_reports_timeout(tmp_path, monkeypatch):
    started = asyncio.Event()

    async def hanging_check(*args):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr("asomforge.runtimes.checks.check_mcp", hanging_check)
    app = create_app(tmp_path)
    resource = hanging_resource(app, tmp_path)
    checked = await CheckService(app.state.service, tmp_path, 0.1, 1).run(resource)
    assert started.is_set()
    assert checked["code"] == "timeout", checked
    assert app.state.service.repository.get("mcp", resource.id).last_check.code == "timeout"


@pytest.mark.asyncio
async def test_closing_http_stream_cancels_mcp_and_does_not_save_result(tmp_path):
    app = create_app(tmp_path)
    resource = hanging_resource(app, tmp_path)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", lifespan="off"))
    thread = Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            await asyncio.sleep(0.02)
        assert server.started
        async with httpx.AsyncClient() as client:
            url = f"http://127.0.0.1:{listener.getsockname()[1]}/api/configurations/mcp/{resource.id}/check"
            async with client.stream("POST", url) as response:
                assert response.status_code == 200
                deadline = time.monotonic() + 5
                while not (tmp_path / "pid").exists() and time.monotonic() < deadline:
                    await asyncio.sleep(0.02)
                assert (tmp_path / "pid").exists()
            pid = int((tmp_path / "pid").read_text())
            deadline = time.monotonic() + 7
            while psutil.pid_exists(pid) and time.monotonic() < deadline:
                await asyncio.sleep(0.05)
            assert not psutil.pid_exists(pid)
            assert app.state.service.repository.get("mcp", resource.id).last_check is None
    finally:
        server.should_exit = True
        await asyncio.to_thread(thread.join, 10)
        listener.close()
