# 处理配置保存、凭据引用、启用切换和检查结果登记。
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from asomforge.domain.configurations import (
    CONFIG_MODELS,
    CheckResult,
    ConfigurationError,
    Draft,
    EnabledChange,
    Kind,
    Resource,
)
from asomforge.domain.ports import ConfigurationRepository


def validation_message(error: ValidationError) -> str:
    return "；".join(
        f"{'.'.join(map(str, item['loc'])) or 'config'}：{item['msg']}"
        for item in error.errors(include_input=False, include_url=False)
    )


class ConfigurationService:
    def __init__(self, repository: ConfigurationRepository):
        self.repository = repository

    def validate(self, kind: Kind, config: dict) -> dict:
        try:
            validated = CONFIG_MODELS[kind].model_validate(config).model_dump(mode="json")
            if kind == "models" and not validated["models"]:
                raise ConfigurationError("请至少添加一个模型后再保存或测试")
            return validated
        except ValidationError as error:
            raise ConfigurationError(validation_message(error)) from error

    def save(
        self,
        kind: Kind,
        draft: Draft,
        resource_id: str | None = None,
        assets: dict[str, bytes] | None = None,
    ) -> Resource:
        config = self.validate(kind, draft.config)
        name = draft.name.strip()
        if not name:
            raise ConfigurationError("名称不能为空")
        with self.repository.transaction():
            previous = self.repository.get(kind, resource_id) if resource_id else None
            if previous and draft.revision != previous.revision:
                raise ConfigurationError("配置已被修改，请刷新后再保存", 409)
            values = self.repository.read_secrets()
            original_values = dict(values)
            previous_refs = previous.secret_refs if previous else {}
            refs = {}
            candidates = {}
            if kind == "models":
                candidates["api_key"] = config.pop("api_key", "")
                config["api_key"] = ""
            if kind in ("mcp", "platforms"):
                for group in ("env", "headers"):
                    for key, value in config.get(group, {}).items():
                        candidates[f"{group}.{key}"] = value
                        config[group][key] = ""
            for field, value in candidates.items():
                if field in draft.clear_secrets:
                    continue
                if not value and field in previous_refs:
                    refs[field] = previous_refs[field]
                elif value or field != "api_key":
                    reference = str(uuid4())
                    values[reference] = value
                    refs[field] = reference
            enabled = previous.enabled if previous else True
            if draft.enabled is not None:
                enabled = draft.enabled
            resource = Resource(
                id=resource_id or str(uuid4()),
                kind=kind,
                name=name,
                description=draft.description,
                enabled=enabled,
                config=config,
                secret_refs=refs,
                revision=previous.revision + 1 if previous else 1,
                created_at=previous.created_at if previous else datetime.now(UTC),
            )
            # New references leave the old credentials valid if the resource write fails.
            self.repository.write_secrets(values)
            try:
                self.repository.put(resource, assets)
            except Exception:
                self.repository.write_secrets(original_values)
                raise
            for unused in set(previous_refs.values()) - set(refs.values()):
                values.pop(unused, None)
            self.repository.write_secrets(values)
            return resource

    def set_enabled(self, kind: Kind, resource_id: str, change: EnabledChange) -> Resource:
        with self.repository.transaction():
            resource = self.repository.get(kind, resource_id)
            if change.revision != resource.revision:
                raise ConfigurationError("配置已被修改，请刷新后再操作", 409)
            if resource.enabled == change.enabled:
                return resource
            updated = resource.model_copy(
                update={
                    "enabled": change.enabled,
                    "revision": resource.revision + 1,
                    "updated_at": datetime.now(UTC),
                    "last_check": None,
                    "model_checks": {},
                }
            )
            self.repository.put(updated)
            return updated

    def delete(self, kind: Kind, resource_id: str) -> None:
        with self.repository.transaction():
            resource = self.repository.get(kind, resource_id)
            self.repository.delete(kind, resource_id)
            values = self.repository.read_secrets()
            for reference in resource.secret_refs.values():
                values.pop(reference, None)
            self.repository.write_secrets(values)

    def resolved(self, resource: Resource) -> dict:
        config = deepcopy(resource.config)
        values = self.repository.read_secrets()
        for field, reference in resource.secret_refs.items():
            if reference not in values:
                raise ConfigurationError("配置引用的本机凭据不存在，请重新填写")
            if "." in field:
                group, key = field.split(".", 1)
                config.setdefault(group, {})[key] = values[reference]
            else:
                config[field] = values[reference]
        return config

    def record_check(self, resource: Resource, result: dict) -> bool:
        with self.repository.transaction():
            try:
                current = self.repository.get(resource.kind, resource.id)
            except ConfigurationError as error:
                if error.status == 404:
                    return False
                raise
            if current.revision != resource.revision:
                return False
            check = CheckResult.model_validate(result)
            current.last_check = check
            if resource.kind == "models" and check.details.get("mode") == "generation":
                current.model_checks[check.details["model_id"]] = check
            self.repository.put(current)
            return True
