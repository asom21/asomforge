# 编排模型发现、草稿凭据解析和指定保存版本的单模型测试。
import asyncio
from datetime import UTC, datetime
from time import monotonic
from typing import TYPE_CHECKING

from pydantic import ValidationError

from asomforge.application.configurations import validation_message
from asomforge.domain.configurations import ConfigurationError, Resource
from asomforge.domain.model_connections import (
    ModelConfig,
    ModelConnectionFailure,
    ModelDiscoverRequest,
    ModelEntry,
    ModelProbeRequest,
    SavedModelProbeRequest,
)
from asomforge.runtimes.model_connections import discover_models, generate_text

if TYPE_CHECKING:
    from asomforge.runtimes.checks import CheckService


class ModelConnectionService:
    def __init__(self, checks: "CheckService"):
        self.checks = checks
        self.service = checks.service

    def draft_config(self, request: ModelDiscoverRequest) -> ModelConfig:
        config = request.config.model_copy(deep=True)
        if request.resource_id is not None:
            with self.service.repository.transaction():
                resource = self.service.repository.get("models", request.resource_id)
                if resource.kind != "models":
                    raise ConfigurationError("引用资源不是模型连接", 404)
                if resource.revision != request.revision:
                    raise ConfigurationError("连接已被修改，请刷新后再使用已保存凭据", 409)
                if not config.api_key and not request.clear_api_key:
                    config.api_key = self.service.resolved(resource).get("api_key", "")
        if request.clear_api_key:
            config.api_key = ""
        return config

    def select(
        self, config: ModelConfig, model_id: str | None, reasoning_effort: str | None
    ) -> ModelEntry:
        selected = (model_id if model_id is not None else config.default_model_id).strip()
        model = next((item for item in config.models if item.id == selected), None)
        if model is None:
            raise ConfigurationError("请先在模型目录中添加并选择要测试的模型")
        if "text" not in model.input_modalities:
            raise ConfigurationError("本次文本测试要求模型声明 text 输入")
        if reasoning_effort is not None:
            if config.protocol == "anthropic-messages":
                raise ConfigurationError("Anthropic 协议暂不支持推理档位参数")
            if (
                not isinstance(model.reasoning_efforts, dict)
                or reasoning_effort not in model.reasoning_efforts
            ):
                raise ConfigurationError("所选推理档位未在该模型中声明")
        return model

    def draft(self, request: ModelProbeRequest) -> tuple:
        config = self.draft_config(request)
        model = self.select(config, request.model_id, request.reasoning_effort)
        return config, model, request.reasoning_effort, None

    def saved(self, resource_id: str, request: SavedModelProbeRequest) -> tuple:
        with self.service.repository.transaction():
            resource = self.service.repository.get("models", resource_id)
            if resource.kind != "models":
                raise ConfigurationError("资源不是模型连接", 404)
            if resource.revision != request.revision:
                raise ConfigurationError("连接已被修改，请刷新后再测试", 409)
            config = ModelConfig.model_validate(self.service.resolved(resource))
            model = self.select(config, request.model_id, request.reasoning_effort)
        return config, model, request.reasoning_effort, resource

    async def discover(self, request: ModelDiscoverRequest) -> list[ModelEntry]:
        config = self.draft_config(request)
        try:
            async with asyncio.timeout(self.checks.timeout), self.checks.slots:
                return await discover_models(config, self.checks.timeout)
        except TimeoutError as error:
            raise ConfigurationError("模型发现超时，已关闭本次连接", 504) from error
        except ModelConnectionFailure as error:
            raise ConfigurationError(
                error.message, 504 if error.code == "timeout" else 502
            ) from error

    async def run(
        self,
        config: ModelConfig,
        model: ModelEntry,
        reasoning_effort: str | None,
        resource: Resource | None,
    ) -> dict:
        started = monotonic()
        try:
            async with asyncio.timeout(self.checks.timeout), self.checks.slots:
                result = await generate_text(config, model, reasoning_effort, self.checks.timeout)
        except TimeoutError:
            result = {
                "status": "failed",
                "code": "timeout",
                "message": "模型测试超时（包含排队），已关闭本次连接",
            }
        except ModelConnectionFailure as error:
            result = error.result()
        details = {
            **result.get("details", {}),
            "mode": "generation",
            "model_id": model.id,
            "latency_ms": round((monotonic() - started) * 1000),
            "persisted": False,
        }
        if model.name:
            details["model_name"] = model.name
        if reasoning_effort is not None:
            details["reasoning_effort"] = reasoning_effort
        result.update(
            resource_id=resource.id if resource else "",
            revision=resource.revision if resource else 0,
            cwd=str(self.checks.root.resolve()),
            checked_at=datetime.now(UTC).isoformat(),
            details=details,
        )
        if resource is not None:
            # The transaction rereads and merges outcomes; no network operation holds its lock.
            details["persisted"] = True
            details["persisted"] = self.service.record_check(resource, result)
        return result

    async def run_default(self, resource: Resource) -> dict:
        try:
            config = ModelConfig.model_validate(self.service.resolved(resource))
            model = self.select(config, None, None)
        except (ConfigurationError, ValidationError) as error:
            message = (
                error.message
                if isinstance(error, ConfigurationError)
                else validation_message(error)
            )
            return {
                "status": "failed",
                "code": "configuration",
                "message": message,
                "resource_id": resource.id,
                "revision": resource.revision,
                "cwd": str(self.checks.root.resolve()),
                "checked_at": datetime.now(UTC).isoformat(),
                "details": {
                    "mode": "generation",
                    "model_id": resource.config.get("default_model_id", ""),
                    "latency_ms": 0,
                    "persisted": False,
                },
            }
        return await self.run(config, model, None, resource)
