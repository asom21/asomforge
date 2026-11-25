# 验证保存失败、凭据隔离、导入元数据和版本边界。
import json

import pytest
from fastapi.testclient import TestClient

from asomforge.domain.configurations import Draft
from asomforge.main import create_app


def test_failed_resource_write_keeps_old_resource_and_credentials(tmp_path, monkeypatch):
    service = create_app(tmp_path).state.service
    old = service.save(
        "models",
        Draft(
            name="original",
            config={
                "base_url": "https://example.com/v1",
                "model": "fixture-model",
                "api_key": "old-secret",
            },
        ),
    )
    secrets_before = service.repository.read_secrets()

    def failed_write(*args):
        raise OSError("controlled disk failure")

    monkeypatch.setattr(service.repository, "put", failed_write)
    with pytest.raises(OSError):
        service.save(
            "models",
            Draft(
                name="changed",
                revision=1,
                config={
                    "base_url": "https://example.com/v1",
                    "model": "fixture-model",
                    "api_key": "new-secret",
                },
            ),
            old.id,
        )
    assert service.repository.get("models", old.id).name == "original"
    assert service.resolved(old)["api_key"] == "old-secret"
    assert service.repository.read_secrets() == secrets_before


def test_batch_import_reports_invalid_item_and_saves_valid_item(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    response = client.post(
        "/api/imports/mcp/commit",
        json={
            "text": json.dumps(
                {
                    "mcpServers": {
                        "valid": {"command": "python", "args": []},
                        "invalid": {"command": "python", "args": "bad"},
                    },
                }
            )
        },
    )
    assert [row["status"] for row in response.json()["results"]] == ["saved", "failed"]
    assert len(client.get("/api/configurations/mcp").json()) == 1


def test_stale_check_cannot_replace_check_on_new_revision(tmp_path):
    service = create_app(tmp_path).state.service
    old = service.save("prompts", Draft(name="prompt", config={"content": "old"}))
    current = service.save(
        "prompts", Draft(name="prompt", revision=1, config={"content": "new"}), old.id
    )
    service.record_check(old, {"status": "passed", "revision": 1})
    assert service.repository.get("prompts", current.id).last_check is None


def test_external_origins_cannot_write_local_configurations(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    response = client.post(
        "/api/configurations/prompts",
        headers={"Origin": "https://example.com"},
        json={"name": "external", "config": {"content": "no"}},
    )
    assert response.status_code == 403
    assert client.get("/api/configurations/prompts").json() == []


def test_missing_credentials_become_a_check_result_not_an_unhandled_stream_error(tmp_path):
    app = create_app(tmp_path)
    client = TestClient(app, base_url="http://127.0.0.1")
    resource = client.post(
        "/api/configurations/models",
        json={
            "name": "missing secret",
            "config": {"base_url": "https://example.com", "api_key": "key", "model": "fixture"},
        },
    ).json()
    app.state.service.repository.write_secrets({})
    response = client.post(f"/api/configurations/models/{resource['id']}/check")
    events = [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]
    assert events[-1]["code"] == "configuration"
    assert events[-1]["status"] == "failed"


def test_source_backup_failure_reports_the_configuration_that_was_saved(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    client = TestClient(app, base_url="http://127.0.0.1")

    def fail_backup(*args):
        raise OSError("controlled backup failure")

    monkeypatch.setattr(app.state.service.repository, "preserve_source", fail_backup)
    response = client.post(
        "/api/imports/mcp/commit",
        json={
            "text": '{"mcpServers":{"example":{"command":"python"}}}',
        },
    )
    row = response.json()["results"][0]
    assert row["status"] == "saved"
    assert row["warning"]
    assert len(client.get("/api/configurations/mcp").json()) == 1


@pytest.mark.parametrize("extra", [{"schema_version": 2}, {"kind": "models"}])
def test_native_import_rejects_incompatible_resource_metadata(tmp_path, extra):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    response = client.post(
        "/api/imports/prompts/preview",
        json={
            "text": json.dumps(
                {
                    "name": "wrong format",
                    "config": {"content": "hello"},
                    **extra,
                }
            )
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_skill_check_resolves_relative_links_with_dot_segments(tmp_path):
    from asomforge.runtimes.checks import CheckService

    app = create_app(tmp_path)
    resource = app.state.service.save(
        "skills",
        Draft(
            name="links",
            config={
                "content": "---\nname: links\ndescription: Example\n---\n"
                "Read [details](./references/details.md#section).",
            },
        ),
        assets={"references/details.md": b"# section"},
    )
    checked = await CheckService(app.state.service, tmp_path, 2, 1).run(resource)
    assert checked["status"] == "passed", checked
