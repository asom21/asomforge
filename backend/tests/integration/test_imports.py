# 验证导入预览、冲突处理、Skill 文件安全与输入校验。
import io
import json
import zipfile

from fastapi.testclient import TestClient

from asomforge.main import create_app


def test_mcp_import_preview_does_not_write_or_echo_secrets(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    source = {
        "mcpServers": {
            "probe": {
                "command": "python",
                "args": ["server.py"],
                "env": {"TOKEN": "hidden-import-value"},
                "customOption": True,
            }
        }
    }
    body = {"text": json.dumps(source)}
    preview = client.post("/api/imports/mcp/preview", json=body)
    assert preview.status_code == 200, preview.text
    assert "hidden-import-value" not in preview.text
    assert preview.json()["items"][0]["warnings"]
    assert client.get("/api/configurations/mcp").json() == []
    committed = client.post("/api/imports/mcp/commit", json=body)
    assert committed.status_code == 200, committed.text
    assert committed.json()["results"][0]["status"] == "saved"
    assert "hidden-import-value" not in committed.text
    original_id = client.get("/api/configurations/mcp").json()[0]["id"]
    copied = client.post("/api/imports/mcp/commit", json={**body, "policy": "copy"})
    assert copied.status_code == 200
    assert len(client.get("/api/configurations/mcp").json()) == 2
    replaced = client.post("/api/imports/mcp/commit", json={**body, "policy": "replace"})
    assert replaced.status_code == 200
    assert replaced.json()["results"][0]["id"] == original_id


def test_mcp_import_rejects_bad_args(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    response = client.post(
        "/api/imports/mcp/preview",
        json={
            "text": '{"mcpServers":{"probe":{"command":"python","args":"wrong"}}}',
        },
    )
    assert response.status_code == 422
    assert "args" in response.text


def skill_archive(extra_path="references/details.md"):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(
            "example-skill/SKILL.md",
            "---\nname: example-skill\ndescription: Example\n---\n"
            "Read [details](references/details.md).\n",
        )
        bundle.writestr(f"example-skill/{extra_path}", "supporting material")
    return archive.getvalue()


def test_skill_import_preserves_package_and_edit_keeps_assets(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    archive = skill_archive()
    response = client.post(
        "/api/imports/skills/commit",
        files={
            "files": ("skill.zip", archive, "application/zip"),
        },
    )
    assert response.status_code == 200, response.text
    resource_id = response.json()["results"][0]["id"]
    resource = client.get(f"/api/configurations/skills/{resource_id}").json()
    assert resource["config"]["skill_name"] == "example-skill"
    files = client.get(f"/api/configurations/skills/{resource_id}/files").json()
    assert {"path": "references/details.md", "size": 19} in files
    resource["config"]["content"] += "\nUpdated instructions.\n"
    changed = client.put(
        f"/api/configurations/skills/{resource_id}",
        json={
            "name": "Renamed display",
            "revision": resource["revision"],
            "config": resource["config"],
        },
    )
    assert changed.status_code == 200, changed.text
    assert (
        tmp_path / "config" / "skills" / resource_id / "example-skill" / "references" / "details.md"
    ).read_text() == "supporting material"


def test_zip_cannot_write_outside_resource(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    response = client.post(
        "/api/imports/skills/commit",
        files={
            "files": ("skill.zip", skill_archive("../../escape.txt"), "application/zip"),
        },
    )
    assert response.status_code == 422
    assert not (tmp_path / "escape.txt").exists()


def test_import_reports_invalid_utf8_as_an_input_error(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    response = client.post(
        "/api/imports/mcp/preview",
        content=b'{"text":"\xff"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert "UTF-8" in response.text
