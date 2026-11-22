# 验证超时和连接断开后，MCP 检查能够释放子进程。
import asyncio
import socket
import sys
import time
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
    app = create_app(tmp_path)
    resource = hanging_resource(app, tmp_path)
    checked = await CheckService(app.state.service, tmp_path, 0.5, 1).run(resource)
    assert checked["code"] == "timeout", checked
    assert not psutil.pid_exists(int((tmp_path / "pid").read_text()))


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
