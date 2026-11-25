# 验证模型文本生成、认证失败、MCP 握手和平台检测结果。
import asyncio
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from fastapi.testclient import TestClient

from asomforge.main import create_app


def result(response):
    assert response.status_code == 200, response.text
    events = [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]
    return events[-1]


@pytest.fixture
def models_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/mcp-auth"):
                self.send_response(401)
            elif self.path != "/v1/chat/completions":
                self.send_response(404)
            elif self.headers.get("Authorization") != "Bearer controlled-key":
                self.send_response(401)
            else:
                self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"choices": [{"message": {"content": "连接成功。"}, "finish_reason": "stop"}]}
                ).encode()
            )

        do_POST = do_GET

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/v1"
    server.shutdown()
    server.server_close()
    thread.join()


def test_model_check_uses_saved_key_and_distinguishes_auth(tmp_path, models_server):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    resource = client.post(
        "/api/configurations/models",
        json={
            "name": "local endpoint",
            "config": {
                "base_url": models_server,
                "api_key": "controlled-key",
                "model": "controlled-model",
            },
        },
    ).json()
    response = client.post(f"/api/configurations/models/{resource['id']}/check")
    checked = result(response)
    assert checked["status"] == "passed"
    assert checked["revision"] == 1
    assert "controlled-key" not in response.text
    assert checked["details"]["mode"] == "generation"
    assert checked["details"]["model_id"] == "controlled-model"
    resource["config"]["api_key"] = "wrong-key"
    client.put(
        f"/api/configurations/models/{resource['id']}",
        json={
            "name": resource["name"],
            "config": resource["config"],
            "revision": 1,
        },
    )
    assert (
        result(client.post(f"/api/configurations/models/{resource['id']}/check"))["code"] == "auth"
    )


def test_stdio_mcp_initializes_and_discovers_without_calling_tools(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    resource = client.post(
        "/api/configurations/mcp",
        json={
            "name": "controlled",
            "config": {
                "command": sys.executable,
                "args": [str(Path(__file__).parents[1] / "fixtures" / "mcp_server.py")],
            },
        },
    ).json()
    checked = result(client.post(f"/api/configurations/mcp/{resource['id']}/check"))
    assert checked["status"] == "passed", checked
    assert checked["details"]["tools"] == 1
    assert (
        client.get(f"/api/configurations/mcp/{resource['id']}").json()["last_check"]["revision"]
        == 1
    )


def test_missing_platform_is_reported_without_installing(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    resource = client.post(
        "/api/configurations/platforms",
        json={
            "name": "unavailable",
            "config": {"platform": "deepseek_harness", "command": "asomforge-missing-fixture"},
        },
    ).json()
    checked = result(client.post(f"/api/configurations/platforms/{resource['id']}/check"))
    assert checked["status"] == "failed"
    assert checked["code"] == "not_installed"


def test_mcp_http_auth_failure_is_reported_without_exposing_headers(tmp_path, models_server):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    resource = client.post(
        "/api/configurations/mcp",
        json={
            "name": "auth",
            "config": {
                "type": "http",
                "url": models_server.replace("/v1", "/mcp-auth"),
                "headers": {"Authorization": "Bearer hidden-probe-token"},
            },
        },
    ).json()
    response = client.post(f"/api/configurations/mcp/{resource['id']}/check")
    assert result(response)["code"] == "auth", response.text
    assert "hidden-probe-token" not in response.text


@pytest.mark.asyncio
async def test_process_timeout_and_cancel_release_child(tmp_path):
    from asomforge.runtimes.processes import run_process

    script = tmp_path / "sleeper.py"
    marker = tmp_path / "pid"
    script.write_text(
        "import os,time,pathlib\n"
        "pathlib.Path(__file__).with_name('pid').write_text(str(os.getpid()))\n"
        "time.sleep(90)\n"
    )
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.5):
            await run_process([sys.executable, str(script)], str(tmp_path), {})
    import psutil

    assert not psutil.pid_exists(int(marker.read_text()))

    marker.unlink()
    task = asyncio.create_task(run_process([sys.executable, str(script)], str(tmp_path), {}))
    for _ in range(100):
        if marker.exists():
            break
        await asyncio.sleep(0.02)
    assert marker.exists()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not psutil.pid_exists(int(marker.read_text()))


@pytest.mark.skipif(os.name != "nt", reason="Windows CLI wrapper")
@pytest.mark.asyncio
async def test_windows_batch_wrapper_with_spaces_can_report_version(tmp_path):
    from asomforge.runtimes.processes import run_process

    folder = tmp_path / "space in path"
    folder.mkdir()
    command = folder / "probe.cmd"
    command.write_text("@echo off\r\necho probe 1.2.3\r\n", encoding="utf-8")
    code, output = await run_process([str(command), "--version"], str(tmp_path), {})
    assert code == 0, output
    assert "1.2.3" in output
