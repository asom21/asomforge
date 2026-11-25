# 实现配置文件、Skill 目录和私密数据的本地读写与替换。
import json
import os
import shutil
import tempfile
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

from asomforge.domain.configurations import KINDS, ConfigurationError, Kind, Resource
from asomforge.domain.model_connections import ModelConfig


def atomic_json(path: Path, value: dict, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        if private:
            os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class FileRepository:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self._lock = RLock()
        for name in (*KINDS, "tools"):
            (self.root / "config" / name).mkdir(parents=True, exist_ok=True)
        (self.root / "private").mkdir(exist_ok=True)
        (self.root / "logs").mkdir(exist_ok=True)

    def transaction(self) -> RLock:
        return self._lock

    def _path(self, kind: Kind, resource_id: str) -> Path:
        try:
            UUID(resource_id)
        except ValueError as error:
            raise ConfigurationError("配置不存在", 404) from error
        base = self.root / "config" / kind
        return (
            base / resource_id / "resource.json"
            if kind == "skills"
            else base / f"{resource_id}.json"
        )

    def list(self, kind: Kind) -> list[Resource]:
        with self._lock:
            base = self.root / "config" / kind
            pattern = "*/resource.json" if kind == "skills" else "*.json"
            resources = [
                self._read(path)
                for path in base.glob(pattern)
                if not path.parent.name.startswith(".")
            ]
            return sorted(resources, key=lambda resource: resource.updated_at, reverse=True)

    def _read(self, path: Path) -> Resource:
        try:
            data = json.loads(path.read_text("utf-8"))
            if data["kind"] == "skills":
                content = path.parent / data["config"]["skill_name"] / "SKILL.md"
                data["config"]["content"] = content.read_text("utf-8")
            if data["kind"] == "models":
                data["config"] = ModelConfig.model_validate(data["config"]).model_dump(mode="json")
            return Resource.model_validate(data)
        except FileNotFoundError as error:
            raise ConfigurationError("配置或配套文件不存在", 404) from error
        except (ValueError, KeyError) as error:
            raise ConfigurationError(f"配置文件不可读：{path.name}", 422) from error

    def get(self, kind: Kind, resource_id: str) -> Resource:
        with self._lock:
            return self._read(self._path(kind, resource_id))

    def put(self, resource: Resource, assets: dict[str, bytes] | None = None) -> None:
        path = self._path(resource.kind, resource.id)
        payload = resource.model_dump(mode="json", exclude={"secret_fields"})
        if resource.kind != "skills":
            atomic_json(path, payload)
            return
        if assets is None and path.exists() and self._read(path).config == resource.config:
            payload["config"].pop("content")
            atomic_json(path, payload)
            return
        if assets is None:
            assets = self.asset_files(resource.id) if path.exists() else {}
        assets = dict(assets)
        assets["SKILL.md"] = payload["config"].pop("content").encode("utf-8")
        container = path.parent
        stage = Path(tempfile.mkdtemp(prefix=".import-", dir=container.parent))
        backup = container.with_name(f".backup-{uuid4()}")
        try:
            package = stage / resource.config["skill_name"]
            package.mkdir()
            for relative, content in assets.items():
                target = (package / relative).resolve()
                if not target.is_relative_to(package.resolve()):
                    raise ConfigurationError("Skill 文件路径超出资源目录")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            atomic_json(stage / "resource.json", payload)
            if container.exists():
                os.replace(container, backup)
            try:
                os.replace(stage, container)
            except OSError:
                if backup.exists():
                    os.replace(backup, container)
                raise
        finally:
            if stage.exists():
                shutil.rmtree(stage)
            if backup.exists() and container.exists():
                shutil.rmtree(backup)

    def delete(self, kind: Kind, resource_id: str) -> None:
        path = self._path(kind, resource_id)
        self.get(kind, resource_id)
        if kind == "skills":
            shutil.rmtree(path.parent)
        else:
            path.unlink()
        (self.root / "private" / "sources" / f"{resource_id}.json").unlink(missing_ok=True)

    def read_secrets(self) -> dict[str, str]:
        path = self.root / "private" / "secrets.json"
        return json.loads(path.read_text("utf-8")) if path.exists() else {}

    def write_secrets(self, values: dict[str, str]) -> None:
        atomic_json(self.root / "private" / "secrets.json", values, private=True)

    def preserve_source(self, resource_id: str, source: dict) -> None:
        atomic_json(self.root / "private" / "sources" / f"{resource_id}.json", source, private=True)

    def asset_files(self, resource_id: str) -> dict[str, bytes]:
        resource = self.get("skills", resource_id)
        root = self._path("skills", resource_id).parent / resource.config["skill_name"]
        result = {}
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ConfigurationError("Skill 资源中不能包含符号链接")
            if path.is_file():
                result[path.relative_to(root).as_posix()] = path.read_bytes()
        return result
