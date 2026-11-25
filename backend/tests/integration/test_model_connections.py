# 验证模型连接协议、草稿凭据隔离和保存版本测试的真实 HTTP 行为。
import asyncio
import gzip
import json
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from asomforge.domain.configurations import Draft, Resource
from asomforge.main import create_app

PROMPT = "请只回复：连接成功。不要执行命令或修改文件。"


@pytest.fixture
def provider():
    state = {"requests": [], "status": 200, "body": None, "delay": 0, "entered": Event()}

    class Handler(BaseHTTPRequestHandler):
        def handle_request(self):
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length)) if length else None
            state["requests"].append((self.command, self.path, dict(self.headers), payload))
            state["entered"].set()
            if state.get("hang"):
                self.connection.settimeout(5)
                try:
                    if self.connection.recv(1) == b"":
                        state["disconnected"].set()
                except (ConnectionResetError, ConnectionAbortedError):
                    state["disconnected"].set()
                return
            if state["delay"]:
                time.sleep(state["delay"])
            body = state["body"]
            if body is None:
                if self.command == "GET":
                    body = {"data": [{"id": "alpha", "display_name": "Alpha"}]}
                elif self.path.endswith("/chat/completions"):
                    body = {
                        "choices": [
                            {"message": {"content": " 连接成功。 "}, "finish_reason": "stop"}
                        ]
                    }
                elif self.path.endswith("/responses"):
                    body = {
                        "status": "completed",
                        "output": [
                            {
                                "type": "message",
                                "content": [{"type": "output_text", "text": "连接成功."}],
                            }
                        ],
                    }
                else:
                    body = {
                        "content": [{"type": "text", "text": "连接成功"}],
                        "stop_reason": "end_turn",
                    }
            raw = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            if state.get("gzip"):
                raw = gzip.compress(raw)
                self.send_header("Content-Encoding", "gzip")
            if state.get("location"):
                self.send_header("Location", state["location"])
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        do_GET = handle_request
        do_POST = handle_request

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state["url"] = f"http://127.0.0.1:{server.server_port}"
    yield state
    server.shutdown()
    server.server_close()
    thread.join()


def config(provider, **changes):
    return {
        "protocol": "openai-chat-completions",
        "base_url": provider["url"] + "/custom/v1",
        "api_key": "fixture-secret",
        "models": [{"id": "alpha", "name": "Alpha", "input_modalities": ["text"]}],
        "default_model_id": "alpha",
        **changes,
    }


def final(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]
    assert events[0]["status"] == "running"
    return events[-1]


def client_for(tmp_path):
    return TestClient(create_app(tmp_path), base_url="http://127.0.0.1")


def save(client, values):
    response = client.post("/api/configurations/models", json={"name": "fixture", "config": values})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize(
    "protocol,path,token_field",
    [
        ("openai-chat-completions", "/custom/v1/chat/completions", "max_completion_tokens"),
        ("openai-responses", "/custom/v1/responses", "max_output_tokens"),
        ("anthropic-messages", "/custom/v1/messages", "max_tokens"),
    ],
)
def test_draft_generation_uses_exact_protocol_and_never_persists(
    tmp_path, provider, protocol, path, token_field
):
    client = client_for(tmp_path)
    values = config(provider, protocol=protocol)
    values["models"][0]["max_output_tokens"] = 99
    checked = final(
        client.post("/api/model-connections/test", json={"config": values, "model_id": "alpha"})
    )
    assert checked["status"] == "passed", checked
    assert checked["resource_id"] == "" and checked["revision"] == 0
    assert checked["details"]["mode"] == "generation"
    assert checked["details"]["model_id"] == "alpha"
    assert checked["details"]["model_name"] == "Alpha"
    assert checked["details"]["latency_ms"] >= 0
    assert checked["details"].get("persisted", False) is False
    assert len(provider["requests"]) == 1
    method, actual_path, headers, payload = provider["requests"][0]
    assert method == "POST" and actual_path == path
    assert payload["model"] == "alpha" and payload[token_field] == 99
    assert "tools" not in payload and payload.get("stream", False) is False
    if protocol == "openai-responses":
        assert payload["input"] == [{"role": "user", "content": PROMPT}]
    else:
        assert payload["messages"] == [{"role": "user", "content": PROMPT}]
    if protocol == "anthropic-messages":
        assert headers["x-api-key"] == "fixture-secret"
        assert headers["anthropic-version"] == "2023-06-01"
        assert "Authorization" not in headers
    else:
        assert headers["Authorization"] == "Bearer fixture-secret"
    assert list((tmp_path / "config" / "models").glob("*.json")) == []
    assert not (tmp_path / "private" / "secrets.json").exists()


@pytest.mark.parametrize(
    "protocol,base_suffix,path",
    [
        ("openai-chat-completions", "/prefix", "/prefix/models"),
        ("openai-responses", "/prefix/v1", "/prefix/v1/models"),
        ("anthropic-messages", "/prefix", "/prefix/v1/models"),
        ("anthropic-messages", "/prefix/v1/", "/prefix/v1/models"),
    ],
)
def test_discovery_allows_empty_catalog_preserves_paths_and_filters_metadata(
    tmp_path, provider, protocol, base_suffix, path
):
    client = client_for(tmp_path)
    provider["body"] = {
        "models": {
            "alpha": {"name": "Alpha", "context_window": 128000},
            "beta": {},
            "bad": {"max_output_tokens": -1},
        }
    }
    values = config(
        provider,
        protocol=protocol,
        base_url=provider["url"] + base_suffix,
        models=[],
        default_model_id="",
    )
    response = client.post("/api/model-connections/discover", json={"config": values})
    assert response.status_code == 200, response.text
    models = response.json()["models"]
    assert [model["id"] for model in models] == ["alpha", "beta", "bad"]
    assert models[0]["context_window"] == 128000
    assert models[0]["input_modalities"] == ["text"]
    assert models[2].get("max_output_tokens") is None
    assert provider["requests"][0][1] == path


@pytest.mark.parametrize(
    "patch",
    [
        {"models": []},
        {"models": [{"id": " "}]},
        {"models": [{"id": "a"}, {"id": " a "}]},
        {"default_model_id": "absent"},
        {"models": [{"id": "a", "context_window": True}]},
        {"models": [{"id": "a", "context_window": 10, "max_output_tokens": 11}]},
        {"models": [{"id": "a", "input_modalities": []}]},
        {"models": [{"id": "a", "reasoning_efforts": {"off": None}}]},
        {"models": [{"id": "a", "reasoning_efforts": {"low": " "}}]},
        {"models": [{"id": "alpha", "reasoning_efforts": 0}]},
        {
            "protocol": "anthropic-messages",
            "models": [{"id": "a", "reasoning_efforts": {"low": "low"}}],
        },
        {"base_url": "http://user:password@127.0.0.1/"},
        {"protocol": []},
    ],
)
def test_save_rejects_invalid_catalog_and_credentials_in_url(tmp_path, provider, patch):
    response = client_for(tmp_path).post(
        "/api/configurations/models", json={"name": "invalid", "config": config(provider, **patch)}
    )
    assert response.status_code == 422, response.text
    assert "password" not in response.text


def test_legacy_reads_normalize_without_rewriting_and_empty_cannot_save_or_test(tmp_path, provider):
    app = create_app(tmp_path)
    client = TestClient(app, base_url="http://127.0.0.1")
    resource = Resource(
        id=str(uuid4()),
        kind="models",
        name="old",
        revision=7,
        config={
            "protocol": "anthropic",
            "base_url": provider["url"],
            "model": " legacy ",
            "api_key": "",
        },
    )
    path = tmp_path / "config" / "models" / f"{resource.id}.json"
    path.write_text(resource.model_dump_json(exclude={"secret_fields"}))
    before = path.read_bytes()
    loaded = client.get(f"/api/configurations/models/{resource.id}").json()
    assert loaded["revision"] == 7
    assert loaded["config"]["protocol"] == "anthropic-messages"
    assert loaded["config"]["models"][0]["id"] == "legacy"
    assert loaded["config"]["default_model_id"] == "legacy"
    assert path.read_bytes() == before
    resource.config["model"] = ""
    path.write_text(resource.model_dump_json(exclude={"secret_fields"}))
    loaded = client.get(f"/api/configurations/models/{resource.id}").json()
    assert loaded["config"]["models"] == []
    assert (
        client.put(
            f"/api/configurations/models/{resource.id}",
            json={"name": "old", "config": loaded["config"], "revision": 7},
        ).status_code
        == 422
    )
    response = client.post(
        f"/api/configurations/models/{resource.id}/test", json={"revision": 7, "model_id": "legacy"}
    )
    assert response.status_code == 422
    assert provider["requests"] == []


def test_draft_credentials_require_matching_model_revision_and_clear_prevents_fallback(
    tmp_path, provider
):
    client = client_for(tmp_path)
    resource = save(client, config(provider))
    draft = {"config": config(provider, api_key=""), "resource_id": resource["id"], "revision": 1}
    response = client.post("/api/model-connections/discover", json=draft)
    assert response.status_code == 200, response.text
    assert provider["requests"][-1][2]["Authorization"] == "Bearer fixture-secret"
    assert "fixture-secret" not in response.text
    for update in [{"clear_api_key": True}, {"resource_id": None, "revision": None}]:
        assert (
            client.post("/api/model-connections/discover", json={**draft, **update}).status_code
            == 200
        )
        assert "Authorization" not in provider["requests"][-1][2]
    count = len(provider["requests"])
    assert (
        client.post(
            "/api/model-connections/discover",
            json={**draft, "revision": 2, "config": config(provider)},
        ).status_code
        == 409
    )
    assert (
        client.post("/api/model-connections/discover", json={**draft, "revision": None}).status_code
        == 422
    )
    prompt = client.post(
        "/api/configurations/prompts", json={"name": "prompt", "config": {"content": "text"}}
    ).json()
    assert (
        client.post(
            "/api/model-connections/discover", json={**draft, "resource_id": prompt["id"]}
        ).status_code
        == 404
    )
    assert len(provider["requests"]) == count
    persisted = client.get(f"/api/configurations/models/{resource['id']}").json()
    assert persisted["last_check"] is None and persisted["model_checks"] == {}


@pytest.mark.parametrize(
    "protocol,selection,expected",
    [
        ("openai-chat-completions", "low", {"reasoning_effort": "small"}),
        ("openai-responses", "low", {"reasoning": {"effort": "small"}}),
        ("openai-chat-completions", "off", {}),
        ("openai-responses", "off", {}),
        ("openai-chat-completions", None, {}),
    ],
)
def test_reasoning_mapping_and_budget_default(tmp_path, provider, protocol, selection, expected):
    values = config(provider, protocol=protocol)
    values["models"][0]["reasoning_efforts"] = {"off": None, "low": "small"}
    request = {"config": values, "model_id": "alpha"}
    if selection is not None:
        request["reasoning_effort"] = selection
    checked = final(client_for(tmp_path).post("/api/model-connections/test", json=request))
    assert checked["status"] == "passed"
    payload = provider["requests"][-1][3]
    actual = {key: payload[key] for key in ("reasoning", "reasoning_effort") if key in payload}
    assert actual == expected
    assert payload.get("max_completion_tokens", payload.get("max_output_tokens")) == 1024


def test_chat_compatibility_field_and_anthropic_reasoning_rejection(tmp_path, provider):
    client = client_for(tmp_path)
    checked = final(
        client.post(
            "/api/model-connections/test",
            json={"config": config(provider, output_token_field="max_tokens"), "model_id": "alpha"},
        )
    )
    assert checked["status"] == "passed"
    assert provider["requests"][-1][3]["max_tokens"] == 1024
    assert "max_completion_tokens" not in provider["requests"][-1][3]
    response = client.post(
        "/api/model-connections/test",
        json={
            "config": config(provider, protocol="anthropic-messages"),
            "model_id": "alpha",
            "reasoning_effort": "low",
        },
    )
    assert response.status_code == 422
    response = client.post(
        "/api/model-connections/test", json={"config": config(provider), "model_id": "absent"}
    )
    assert response.status_code == 422
    assert len(provider["requests"]) == 1


@pytest.mark.parametrize(
    "body,status,code",
    [
        (
            {"choices": [{"message": {"content": "different"}, "finish_reason": "stop"}]},
            "limited",
            "unexpected_text",
        ),
        (
            {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]},
            "limited",
            "empty_response",
        ),
        (
            {
                "choices": [
                    {
                        "message": {"content": "连接成功", "tool_calls": [{"id": "call"}]},
                        "finish_reason": "tool_calls",
                    }
                ]
            },
            "limited",
            "tool_response",
        ),
        (
            {"choices": [{"message": {"content": "连接成功"}, "finish_reason": "length"}]},
            "limited",
            "output_limit",
        ),
        (
            {"choices": [{"message": {"content": "连接成功！"}, "finish_reason": "stop"}]},
            "limited",
            "unexpected_text",
        ),
        ({"unexpected": "secret provider raw body"}, "failed", "protocol"),
        ({"choices": [{"message": {"content": 0}}]}, "failed", "protocol"),
    ],
)
def test_generation_classifies_text_tools_empty_truncation_and_protocol(
    tmp_path, provider, body, status, code
):
    provider["body"] = body
    checked = final(
        client_for(tmp_path).post(
            "/api/model-connections/test", json={"config": config(provider), "model_id": "alpha"}
        )
    )
    assert (checked["status"], checked["code"]) == (status, code)
    assert "secret provider raw body" not in json.dumps(checked)


@pytest.mark.parametrize(
    "http_status,body,code",
    [
        (401, {"error": "fixture-secret raw-body"}, "auth"),
        (403, {}, "auth"),
        (404, {"error": {"code": "model_not_found"}}, "model"),
        (404, {}, "protocol"),
        (400, {}, "parameters"),
        (429, {}, "rate_limit"),
        (500, {}, "provider"),
        (302, {}, "protocol"),
    ],
)
def test_provider_errors_are_sanitized_and_never_retried(
    tmp_path, provider, http_status, body, code
):
    provider["status"], provider["body"] = http_status, body
    provider["location"] = provider["url"] + "/redirect-target"
    response = client_for(tmp_path).post(
        "/api/model-connections/test", json={"config": config(provider), "model_id": "alpha"}
    )
    checked = final(response)
    assert checked["status"] == "failed" and checked["code"] == code
    assert "fixture-secret" not in response.text and "raw-body" not in response.text
    assert len(provider["requests"]) == 1


@pytest.mark.parametrize("operation", ["test", "discover"])
def test_decompressed_response_limit(tmp_path, provider, operation):
    provider["body"] = b"x" * (4 * 1024 * 1024 + 1)
    provider["gzip"] = True
    response = client_for(tmp_path).post(
        f"/api/model-connections/{operation}",
        json={"config": config(provider), **({"model_id": "alpha"} if operation == "test" else {})},
    )
    if operation == "test":
        assert final(response)["code"] == "response_too_large"
    else:
        assert response.status_code == 502
    assert len(provider["requests"]) == 1


def test_saved_results_merge_and_updates_clear_all_model_checks(tmp_path, provider):
    client = client_for(tmp_path)
    values = config(provider)
    values["models"].append({"id": "beta", "input_modalities": ["text"]})
    resource = save(client, values)
    for model_id in ("alpha", "beta"):
        checked = final(
            client.post(
                f"/api/configurations/models/{resource['id']}/test",
                json={"revision": 1, "model_id": model_id},
            )
        )
        assert checked["details"]["persisted"] is True
    loaded = client.get(f"/api/configurations/models/{resource['id']}").json()
    assert set(loaded["model_checks"]) == {"alpha", "beta"}
    assert loaded["last_check"]["details"]["model_id"] == "beta"
    checked = final(client.post(f"/api/configurations/models/{resource['id']}/check"))
    assert checked["details"]["model_id"] == "alpha"
    response = client.put(
        f"/api/configurations/models/{resource['id']}",
        json={"name": "updated", "revision": 1, "config": resource["config"]},
    )
    assert response.status_code == 200
    assert response.json()["model_checks"] == {} and response.json()["last_check"] is None
    assert (
        client.post(
            f"/api/configurations/models/{resource['id']}/test",
            json={"revision": 1, "model_id": "alpha"},
        ).status_code
        == 409
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["update", "delete", "cancel"])
async def test_inflight_mutation_or_cancel_never_corrupts_saved_resource(
    tmp_path, provider, mutation
):
    from asomforge.application.model_connections import ModelConnectionService
    from asomforge.domain.model_connections import SavedModelProbeRequest
    from asomforge.runtimes.checks import CheckService

    app = create_app(tmp_path)
    service = app.state.service
    resource = service.save("models", Draft(name="fixture", config=config(provider)))
    checks = CheckService(service, tmp_path, 2, 1)
    models = ModelConnectionService(checks)
    prepared = models.saved(resource.id, SavedModelProbeRequest(revision=1, model_id="alpha"))
    provider["delay"] = 0.2
    task = asyncio.create_task(models.run(*prepared))
    assert await asyncio.to_thread(provider["entered"].wait, 2)
    if mutation == "update":
        service.save("models", Draft(name="new", config=resource.config, revision=1), resource.id)
    elif mutation == "delete":
        service.delete("models", resource.id)
    else:
        task.cancel()
    if mutation == "cancel":
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        checked = await task
        assert checked["details"]["persisted"] is False
    if mutation != "delete":
        current = service.repository.get("models", resource.id)
        assert current.last_check is None and current.model_checks == {}


@pytest.mark.asyncio
async def test_timeout_includes_shared_concurrency_queue_and_releases_slot(tmp_path, provider):
    from asomforge.application.model_connections import ModelConnectionService
    from asomforge.domain.model_connections import ModelProbeRequest
    from asomforge.runtimes.checks import CheckService

    app = create_app(tmp_path)
    checks = CheckService(app.state.service, tmp_path, 0.05, 1)
    models = ModelConnectionService(checks)
    request = ModelProbeRequest(config=config(provider), model_id="alpha")
    prepared = models.draft(request)
    await checks.slots.acquire()
    try:
        result = await models.run(*prepared)
        assert result["code"] == "timeout"
        assert provider["requests"] == []
    finally:
        checks.slots.release()
    provider["delay"] = 0.2
    result = await models.run(*prepared)
    assert result["code"] == "timeout"
    assert checks.slots.locked() is False


@pytest.mark.asyncio
async def test_closing_saved_sse_cancels_upstream_http_and_does_not_save(tmp_path, provider):
    import httpx
    import uvicorn

    app = create_app(tmp_path)
    resource = app.state.service.save("models", Draft(name="fixture", config=config(provider)))
    provider["hang"] = True
    provider["disconnected"] = Event()
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
            url = f"http://127.0.0.1:{listener.getsockname()[1]}/api/configurations/models/{resource.id}/test"
            async with client.stream(
                "POST", url, json={"revision": 1, "model_id": "alpha"}
            ) as response:
                assert response.status_code == 200
                assert await asyncio.to_thread(provider["entered"].wait, 3)
            assert await asyncio.to_thread(provider["disconnected"].wait, 3)
        current = app.state.service.repository.get("models", resource.id)
        assert current.last_check is None and current.model_checks == {}
    finally:
        server.should_exit = True
        await asyncio.to_thread(thread.join, 5)
        listener.close()


@pytest.mark.asyncio
async def test_concurrent_same_version_model_tests_merge_outcomes(tmp_path, provider):
    from asomforge.application.model_connections import ModelConnectionService
    from asomforge.domain.model_connections import SavedModelProbeRequest
    from asomforge.runtimes.checks import CheckService

    service = create_app(tmp_path).state.service
    values = config(provider)
    values["models"].append({"id": "beta"})
    resource = service.save("models", Draft(name="fixture", config=values))
    models = ModelConnectionService(CheckService(service, tmp_path, 3, 3))
    provider["delay"] = 0.1
    prepared = [
        models.saved(resource.id, SavedModelProbeRequest(revision=1, model_id=model_id))
        for model_id in ("alpha", "beta")
    ]
    results = await asyncio.gather(*(models.run(*probe) for probe in prepared))
    assert all(result["details"]["persisted"] for result in results)
    current = service.repository.get("models", resource.id)
    assert set(current.model_checks) == {"alpha", "beta"}


@pytest.mark.parametrize(
    "protocol,body,code",
    [
        (
            "openai-responses",
            {"output": [{"type": "function_call", "arguments": "danger"}], "status": "completed"},
            "tool_response",
        ),
        ("openai-responses", {"output": [], "status": "incomplete"}, "output_limit"),
        (
            "anthropic-messages",
            {
                "content": [{"type": "tool_use", "input": {"command": "danger"}}],
                "stop_reason": "tool_use",
            },
            "tool_response",
        ),
        ("anthropic-messages", {"content": [], "stop_reason": "max_tokens"}, "output_limit"),
    ],
)
def test_other_protocols_do_not_treat_tools_or_budget_exhaustion_as_success(
    tmp_path, provider, protocol, body, code
):
    provider["body"] = body
    checked = final(
        client_for(tmp_path).post(
            "/api/model-connections/test",
            json={"config": config(provider, protocol=protocol), "model_id": "alpha"},
        )
    )
    assert checked["status"] == "limited" and checked["code"] == code
    assert len(provider["requests"]) == 1


def test_default_selection_preview_redaction_and_length(tmp_path, provider):
    provider["body"] = {"choices": [{"message": {"content": "fixture-secret" + "x" * 300}}]}
    checked = final(
        client_for(tmp_path).post("/api/model-connections/test", json={"config": config(provider)})
    )
    assert checked["details"]["model_id"] == "alpha"
    assert "fixture-secret" not in json.dumps(checked)
    assert len(checked["details"]["response_preview"]) <= 240


def test_import_accepts_legacy_and_new_catalog_but_never_imports_test_metadata(tmp_path, provider):
    client = client_for(tmp_path)
    response = client.post(
        "/api/imports/models/commit",
        json={
            "text": json.dumps(
                {
                    "resources": [
                        {
                            "name": "legacy",
                            "config": {
                                "protocol": "openai",
                                "base_url": provider["url"],
                                "model": "alpha",
                            },
                            "last_check": {"status": "passed"},
                            "model_checks": {"alpha": {"status": "passed"}},
                        },
                        {"name": "new", "config": config(provider)},
                    ]
                }
            )
        },
    )
    assert response.status_code == 200, response.text
    assert [row["status"] for row in response.json()["results"]] == ["saved", "saved"]
    for resource in client.get("/api/configurations/models").json():
        assert resource["config"]["protocol"] == "openai-chat-completions"
        assert resource["config"]["models"][0]["id"] == "alpha"
        assert resource["last_check"] is None and resource["model_checks"] == {}


@pytest.mark.parametrize("operation", ["test", "discover"])
def test_deeply_nested_provider_json_is_a_sanitized_protocol_failure(tmp_path, provider, operation):
    provider["body"] = b'{"provider_private_payload_752":' * 10000 + b"0" + b"}" * 10000
    response = client_for(tmp_path).post(
        f"/api/model-connections/{operation}",
        json={"config": config(provider), **({"model_id": "alpha"} if operation == "test" else {})},
    )
    if operation == "test":
        assert final(response)["code"] == "protocol"
    else:
        assert response.status_code == 502
    assert "provider_private_payload_752" not in response.text


def test_draft_using_saved_credentials_never_writes_resource_key_or_result(tmp_path, provider):
    client = client_for(tmp_path)
    resource = save(client, config(provider))
    resource_path = tmp_path / "config" / "models" / f"{resource['id']}.json"
    secrets_path = tmp_path / "private" / "secrets.json"
    before_resource, before_secrets = resource_path.read_bytes(), secrets_path.read_bytes()
    checked = final(
        client.post(
            "/api/model-connections/test",
            json={
                "config": config(provider, api_key=""),
                "resource_id": resource["id"],
                "revision": 1,
                "model_id": "alpha",
            },
        )
    )
    assert (
        checked["status"] == "passed" and checked["resource_id"] == "" and checked["revision"] == 0
    )
    assert checked["details"]["persisted"] is False
    assert provider["requests"][0][2]["Authorization"] == "Bearer fixture-secret"
    assert resource_path.read_bytes() == before_resource
    assert secrets_path.read_bytes() == before_secrets


def test_enable_change_invalidates_all_model_results(tmp_path, provider):
    client = client_for(tmp_path)
    resource = save(client, config(provider))
    assert (
        final(client.post(f"/api/configurations/models/{resource['id']}/check"))["status"]
        == "passed"
    )
    response = client.patch(
        f"/api/configurations/models/{resource['id']}", json={"revision": 1, "enabled": False}
    )
    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert response.json()["model_checks"] == {} and response.json()["last_check"] is None


def test_refused_connection_is_network_failure_without_credential_leak(tmp_path, provider):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        values = config(provider, base_url=f"http://127.0.0.1:{listener.getsockname()[1]}/v1")
        response = client_for(tmp_path).post("/api/model-connections/test", json={"config": values})
    checked = final(response)
    assert checked["status"] == "failed" and checked["code"] == "network"
    assert "fixture-secret" not in response.text


@pytest.mark.asyncio
async def test_closing_discovery_request_cancels_upstream_http_and_never_writes(tmp_path, provider):
    import uvicorn

    app = create_app(tmp_path)
    resource = app.state.service.save("models", Draft(name="fixture", config=config(provider)))
    resource_path = tmp_path / "config" / "models" / f"{resource.id}.json"
    secrets_path = tmp_path / "private" / "secrets.json"
    before_resource, before_secrets = resource_path.read_bytes(), secrets_path.read_bytes()
    provider["hang"] = True
    provider["disconnected"] = Event()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            log_level="critical",
            lifespan="off",
            timeout_graceful_shutdown=1,
        )
    )
    thread = Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            await asyncio.sleep(0.02)
        assert server.started
        _, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            body = json.dumps(
                {
                    "config": config(provider, api_key=""),
                    "resource_id": resource.id,
                    "revision": 1,
                }
            ).encode()
            writer.write(
                (
                    f"POST /api/model-connections/discover HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                    f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
                ).encode()
                + body
            )
            await writer.drain()
            assert await asyncio.to_thread(provider["entered"].wait, 3)
        finally:
            writer.close()
            await writer.wait_closed()
        assert await asyncio.to_thread(provider["disconnected"].wait, 1)
        assert resource_path.read_bytes() == before_resource
        assert secrets_path.read_bytes() == before_secrets
    finally:
        server.should_exit = True
        await asyncio.to_thread(thread.join, 5)
        listener.close()


def test_discovery_omits_secret_ids_and_redacts_secret_names(tmp_path, provider):
    client = client_for(tmp_path)
    resource = save(client, config(provider))
    provider["body"] = {
        "data": [
            {"id": "echo-fixture-secret-model", "name": "unsafe id"},
            {"id": "safe", "name": "Echo fixture-secret here"},
            {"id": "normal", "name": "Normal"},
        ]
    }
    response = client.post(
        "/api/model-connections/discover",
        json={
            "config": config(provider, api_key=""),
            "resource_id": resource["id"],
            "revision": 1,
        },
    )
    assert response.status_code == 200, response.text
    assert "fixture-secret" not in response.text
    assert [entry["id"] for entry in response.json()["models"]] == ["safe", "normal"]
    assert response.json()["models"][1]["name"] == "Normal"


@pytest.mark.parametrize("status", ["failed", "cancelled", "in_progress", "queued", "unknown"])
def test_responses_non_success_status_never_passes_even_with_success_text(
    tmp_path, provider, status
):
    provider["body"] = {
        "status": status,
        "error": {"message": "fixture-secret raw-provider-error"},
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "连接成功"}]}],
    }
    response = client_for(tmp_path).post(
        "/api/model-connections/test",
        json={
            "config": config(provider, protocol="openai-responses"),
            "model_id": "alpha",
        },
    )
    checked = final(response)
    assert checked["status"] == "failed" and checked["code"] == "protocol"
    assert "fixture-secret" not in response.text and "raw-provider-error" not in response.text


@pytest.mark.parametrize("include_status", [True, False])
def test_responses_completed_or_compatible_missing_status_accepts_valid_text(
    tmp_path, provider, include_status
):
    provider["body"] = {
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "连接成功"}]}],
    }
    if include_status:
        provider["body"]["status"] = "completed"
    checked = final(
        client_for(tmp_path).post(
            "/api/model-connections/test",
            json={
                "config": config(provider, protocol="openai-responses"),
                "model_id": "alpha",
            },
        )
    )
    assert checked["status"] == "passed"
