# 校验导入条目并处理同名配置的跳过、替换与另存。
import json
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from pydantic import ValidationError

from asomforge.application.configurations import ConfigurationService, validation_message
from asomforge.application.skills import skill_packages
from asomforge.domain.configurations import CONFIG_MODELS, ConfigurationError, Draft, Kind


@dataclass
class ImportItem:
    name: str
    draft: Draft | None = None
    source: dict = field(default_factory=dict)
    assets: dict[str, bytes] | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def parse_json(text: str):
    try:
        return json.loads(text)
    except (ValueError, TypeError) as error:
        raise ConfigurationError("JSON 格式错误，请检查引号、逗号和括号") from error


class ImportService:
    def __init__(self, service: ConfigurationService, size_limit: int):
        self.service = service
        self.size_limit = size_limit

    def parse(self, kind: Kind, text: str, files: dict[str, bytes]) -> list[ImportItem]:
        if kind == "skills" and files:
            return [
                self._item(kind, draft, {}, assets)
                for draft, assets in skill_packages(files, self.size_limit)
            ]
        sources = [(name, value.decode("utf-8-sig")) for name, value in files.items()]
        if text:
            sources.append(("import.json", text))
        if not sources:
            raise ConfigurationError("请选择导入文件或粘贴配置内容")
        items = []
        for filename, content in sources:
            if kind == "prompts" and PurePosixPath(filename).suffix.lower() in (".md", ".txt"):
                items.append(
                    self._item(
                        kind,
                        {
                            "name": PurePosixPath(filename).stem,
                            "config": {"content": content},
                        },
                        {},
                    )
                )
                continue
            source = parse_json(content)
            if kind == "mcp":
                servers = source.get("mcpServers") if isinstance(source, dict) else None
                if not isinstance(servers, dict) or not servers:
                    raise ConfigurationError("MCP 导入需要非空的 mcpServers 对象")
                for name, config in servers.items():
                    if not isinstance(config, dict):
                        items.append(ImportItem(name, error="MCP 配置必须是对象"))
                        continue
                    known = CONFIG_MODELS[kind].model_fields
                    unknown = sorted(set(config) - set(known))
                    item = self._item(
                        kind,
                        {
                            "name": name,
                            "config": {key: value for key, value in config.items() if key in known},
                        },
                        config,
                    )
                    if unknown:
                        item.warnings.append(
                            "扩展字段仅保留在私有来源文件，不参与连接：" + "、".join(unknown)
                        )
                    items.append(item)
            else:
                entries = source.get("resources", [source]) if isinstance(source, dict) else source
                if not isinstance(entries, list):
                    raise ConfigurationError("导入内容需要资源对象或 resources 数组")
                for entry in entries:
                    if not isinstance(entry, dict):
                        items.append(ImportItem("无效条目", error="资源必须是对象"))
                        continue
                    if entry.get("schema_version", 1) != 1 or entry.get("kind", kind) != kind:
                        items.append(
                            ImportItem(
                                entry.get("name", "未命名"),
                                error="资源版本或类型与当前导入分类不匹配",
                            )
                        )
                        continue
                    items.append(
                        self._item(
                            kind,
                            {
                                key: entry[key]
                                for key in ("name", "description", "config", "enabled")
                                if key in entry
                            },
                            entry,
                        )
                    )
        return items

    def _item(self, kind, payload, source, assets=None) -> ImportItem:
        name = payload.get("name", "未命名")
        try:
            draft = Draft.model_validate(payload)
            if not draft.name.strip():
                raise ConfigurationError("名称不能为空")
            draft.config = self.service.validate(kind, draft.config)
            return ImportItem(name, draft, source, assets)
        except (ValidationError, ConfigurationError) as error:
            message = (
                validation_message(error) if isinstance(error, ValidationError) else error.message
            )
            return ImportItem(name, error=message)

    def preview(self, kind: Kind, items: list[ImportItem]) -> dict:
        if not any(item.draft for item in items):
            raise ConfigurationError("；".join(item.error or "无有效条目" for item in items))
        existing = self.service.repository.list(kind)
        return {
            "items": [
                {
                    "name": item.name,
                    "warnings": item.warnings,
                    "error": item.error,
                    "conflict": next((row.id for row in existing if row.name == item.name), None),
                    "files": list(item.assets or {}),
                }
                for item in items
            ]
        }

    def commit(self, kind: Kind, items: list[ImportItem], policy: str) -> dict:
        if policy not in ("skip", "replace", "copy"):
            raise ConfigurationError("冲突策略必须为 skip、replace 或 copy")
        results = []
        for item in items:
            if item.error:
                results.append({"name": item.name, "status": "failed", "error": item.error})
                continue
            with self.service.repository.transaction():
                existing = self.service.repository.list(kind)
                conflicts = [row for row in existing if row.name == item.name]
                if len(conflicts) > 1 and policy == "replace":
                    results.append(
                        {
                            "name": item.name,
                            "status": "failed",
                            "error": "存在多个同名配置，请先重命名后再替换",
                        }
                    )
                    continue
                previous = conflicts[0] if conflicts else None
                if previous and policy == "skip":
                    results.append({"name": item.name, "status": "skipped", "id": previous.id})
                    continue
                draft = item.draft.model_copy(deep=True)
                if previous and policy == "copy":
                    names = {row.name for row in existing}
                    suffix = 2
                    while f"{item.name} ({suffix})" in names:
                        suffix += 1
                    draft.name = f"{item.name} ({suffix})"
                    previous = None
                draft.revision = previous.revision if previous else None
                try:
                    resource = self.service.save(
                        kind, draft, previous.id if previous else None, item.assets
                    )
                    row = {"name": resource.name, "status": "saved", "id": resource.id}
                    if item.source:
                        try:
                            self.service.repository.preserve_source(resource.id, item.source)
                        except OSError:
                            row["warning"] = "配置已保存，但原始来源副本写入失败"
                    results.append(row)
                except (ConfigurationError, OSError) as error:
                    message = (
                        error.message if isinstance(error, ConfigurationError) else "文件保存失败"
                    )
                    results.append({"name": item.name, "status": "failed", "error": message})
        return {"results": results}
