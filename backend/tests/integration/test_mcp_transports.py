# 使用受控服务验证 Streamable HTTP 和 SSE 的 MCP 连接。
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_checks import result

from asomforge.main import create_app


@pytest.mark.parametrize(
    ("kind", "transport", "path"),
    [
        ("http", "streamable-http", "/mcp"),
        ("sse", "sse", "/sse"),
    ],
)
def test_http_mcp_transports_initialize_and_discover(tmp_path, kind, transport, path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).parents[1] / "fixtures" / "mcp_server.py"),
            "--transport",
            transport,
            "--port",
            str(port),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)
        client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
        resource = client.post(
            "/api/configurations/mcp",
            json={
                "name": transport,
                "config": {"type": kind, "url": f"http://127.0.0.1:{port}{path}"},
            },
        ).json()
        checked = result(client.post(f"/api/configurations/mcp/{resource['id']}/check"))
        assert checked["status"] == "passed", checked
        assert checked["details"]["tools"] == 1
    finally:
        server.terminate()
        server.wait(timeout=5)
