# 验证配置持久化、版本冲突以及凭据的保存与清除。
import json

from fastapi.testclient import TestClient

from asomforge.main import create_app


def test_prompt_survives_restart(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    saved = client.post(
        "/api/configurations/prompts",
        json={
            "name": "需求分析",
            "config": {"content": "分析 {{goal}}", "variables": ["goal"]},
        },
    )
    assert saved.status_code == 201, saved.text
    resource = saved.json()
    reopened = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    assert reopened.get("/api/configurations/prompts").json()[0]["name"] == "需求分析"
    changed = reopened.put(
        f"/api/configurations/prompts/{resource['id']}",
        json={
            "name": "新名称",
            "revision": resource["revision"],
            "config": {"content": "测试", "variables": []},
        },
    )
    assert changed.status_code == 200
    assert changed.json()["id"] == resource["id"]
    assert changed.json()["revision"] == 2
    conflict = client.put(
        f"/api/configurations/prompts/{resource['id']}",
        json={
            "name": "过期修改",
            "revision": 1,
            "config": {"content": "错误", "variables": []},
        },
    )
    assert conflict.status_code == 409


def test_credentials_are_private_and_can_be_preserved_or_removed(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    saved = client.post(
        "/api/configurations/models",
        json={
            "name": "本地模型",
            "config": {
                "protocol": "openai",
                "base_url": "http://localhost:1234/v1",
                "model": "example",
                "api_key": "test-private-value",
            },
        },
    )
    assert saved.status_code == 201, saved.text
    assert "test-private-value" not in saved.text
    resource = saved.json()
    assert resource["secret_fields"] == ["api_key"]
    files = list((tmp_path / "config" / "models").glob("*.json"))
    assert len(files) == 1
    assert "test-private-value" not in files[0].read_text("utf-8")
    assert "test-private-value" in json.dumps(
        json.loads((tmp_path / "private" / "secrets.json").read_text("utf-8"))
    )
    updated = client.put(
        f"/api/configurations/models/{resource['id']}",
        json={
            "name": "改名",
            "revision": 1,
            "config": resource["config"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["secret_fields"] == ["api_key"]
    cleared = client.put(
        f"/api/configurations/models/{resource['id']}",
        json={
            "name": "改名",
            "revision": 2,
            "config": resource["config"],
            "clear_secrets": ["api_key"],
        },
    )
    assert cleared.status_code == 200
    assert cleared.json()["secret_fields"] == []


def test_invalid_configuration_does_not_create_files(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    response = client.post(
        "/api/configurations/mcp",
        json={
            "name": "错误输入",
            "config": {"command": "python", "args": "not-an-array"},
        },
    )
    assert response.status_code == 422
    assert "args" in response.text
    assert not list((tmp_path / "config" / "mcp").glob("*.json"))
    assert (
        client.post(
            "/api/configurations/tools",
            json={
                "name": "工具",
                "config": {},
            },
        ).status_code
        == 404
    )
