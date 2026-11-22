# 验证启用状态持久化、编辑兼容及凭据和 Skill 文件保留。
import json

from fastapi.testclient import TestClient

from asomforge.main import create_app


def test_legacy_configuration_defaults_to_enabled_and_toggle_survives_restart_and_edit(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    resource = client.post(
        "/api/configurations/prompts",
        json={
            "name": "switch",
            "config": {"content": "hello"},
        },
    ).json()
    path = tmp_path / "config/prompts" / f"{resource['id']}.json"
    legacy = json.loads(path.read_text(encoding="utf-8"))
    legacy.pop("enabled", None)
    path.write_text(json.dumps(legacy), encoding="utf-8")
    url = f"/api/configurations/prompts/{resource['id']}"
    assert client.get(url).json()["enabled"] is True

    response = client.patch(url, json={"enabled": False, "revision": resource["revision"]})
    assert response.status_code == 200, response.text
    assert response.json()["enabled"] is False
    assert response.json()["revision"] == resource["revision"] + 1
    reopened = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    disabled = reopened.get(url).json()
    assert disabled["enabled"] is False
    assert json.loads(path.read_text(encoding="utf-8"))["enabled"] is False
    edited = reopened.put(
        url,
        json={
            "name": "edited",
            "config": disabled["config"],
            "revision": disabled["revision"],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["enabled"] is False
    assert (
        client.patch(url, json={"enabled": True, "revision": resource["revision"]}).status_code
        == 409
    )
    assert (
        client.patch(
            url, json={"enabled": "false", "revision": edited.json()["revision"]}
        ).status_code
        == 422
    )
    assert reopened.get(url).json()["enabled"] is False


def test_toggle_preserves_private_credentials_and_noop_does_not_change_revision(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    resource = client.post(
        "/api/configurations/models",
        json={
            "name": "model",
            "config": {"base_url": "https://example.com/v1", "api_key": "controlled-private-key"},
        },
    ).json()
    secrets_path = tmp_path / "private/secrets.json"
    secrets = secrets_path.read_bytes()
    url = f"/api/configurations/models/{resource['id']}"
    changed = client.patch(url, json={"enabled": False, "revision": resource["revision"]})
    assert changed.status_code == 200, changed.text
    assert changed.json()["config"] == resource["config"]
    assert changed.json()["secret_refs"] == resource["secret_refs"]
    assert secrets_path.read_bytes() == secrets
    assert "controlled-private-key" not in changed.text
    unchanged = client.patch(url, json={"enabled": False, "revision": changed.json()["revision"]})
    assert unchanged.status_code == 200
    assert unchanged.json()["revision"] == changed.json()["revision"]


def test_skill_toggle_keeps_supporting_files_and_failed_write_keeps_old_state(
    tmp_path, monkeypatch
):
    app = create_app(tmp_path)
    client = TestClient(app, base_url="http://127.0.0.1")
    resource = client.post(
        "/api/configurations/skills",
        json={
            "name": "skill",
            "config": {"content": "---\nname: example\ndescription: Example\n---\nBody"},
        },
    ).json()
    package = tmp_path / "config/skills" / resource["id"] / "example"
    support = package / "references/details.md"
    support.parent.mkdir()
    support.write_bytes(b"supporting material")
    before = {
        path.relative_to(package): path.read_bytes()
        for path in package.rglob("*")
        if path.is_file()
    }
    url = f"/api/configurations/skills/{resource['id']}"
    disabled = client.patch(url, json={"enabled": False, "revision": resource["revision"]})
    assert disabled.status_code == 200, disabled.text
    assert {
        path.relative_to(package): path.read_bytes()
        for path in package.rglob("*")
        if path.is_file()
    } == before

    def fail_write(*args):
        raise OSError("controlled disk failure")

    monkeypatch.setattr(app.state.service.repository, "put", fail_write)
    failed = client.patch(url, json={"enabled": True, "revision": disabled.json()["revision"]})
    assert failed.status_code == 500
    assert client.get(url).json()["enabled"] is False


def test_native_import_preserves_explicit_disabled_state(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    response = client.post(
        "/api/imports/prompts/commit",
        json={
            "text": json.dumps(
                {
                    "name": "disabled import",
                    "enabled": False,
                    "config": {"content": "hello"},
                }
            )
        },
    )
    assert response.status_code == 200, response.text
    assert client.get("/api/configurations/prompts").json()[0]["enabled"] is False
