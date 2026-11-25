# 定义多模型连接、能力声明和草稿测试请求的运行时校验。
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

Protocol = Literal["openai-chat-completions", "openai-responses", "anthropic-messages"]
ReasoningEffort = Literal["off", "minimal", "low", "medium", "high", "xhigh"]
PositiveInt = Annotated[StrictInt, Field(gt=0)]


class ModelContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelEntry(ModelContract):
    id: StrictStr
    name: StrictStr | None = None
    context_window: PositiveInt | None = None
    max_output_tokens: PositiveInt | None = None
    input_modalities: list[Literal["text", "image"]] = Field(default_factory=lambda: ["text"])
    reasoning_efforts: Literal[False] | dict[ReasoningEffort, StrictStr | None] = False

    @field_validator("reasoning_efforts", mode="before")
    @classmethod
    def strict_reasoning_declaration(cls, value):
        if value is not False and not isinstance(value, dict):
            raise ValueError("推理能力必须为 false 或档位映射")
        return value

    @field_validator("id")
    @classmethod
    def nonempty_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("模型 ID 不能为空")
        return value

    @model_validator(mode="after")
    def validate_capabilities(self) -> Self:
        if not self.input_modalities or len(set(self.input_modalities)) != len(
            self.input_modalities
        ):
            raise ValueError("输入类型至少一个且不能重复")
        if self.context_window and self.max_output_tokens:
            if self.max_output_tokens > self.context_window:
                raise ValueError("最大输出不能超过上下文窗口")
        if self.reasoning_efforts is not False:
            if not any(effort != "off" for effort in self.reasoning_efforts):
                raise ValueError("推理档位至少需要一个非 off 档位")
            for effort, value in self.reasoning_efforts.items():
                if (effort != "off" and value is None) or (value is not None and not value.strip()):
                    raise ValueError("非 off 推理档位需要非空 API 值；off 可使用 null")
        return self


class ModelConfig(ModelContract):
    protocol: Protocol = "openai-chat-completions"
    base_url: HttpUrl
    api_key: StrictStr = ""
    output_token_field: Literal["max_completion_tokens", "max_tokens"] = "max_completion_tokens"
    models: list[ModelEntry] = Field(default_factory=list)
    default_model_id: StrictStr = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy(cls, value):
        if not isinstance(value, dict):
            return value
        data = dict(value)
        protocol = data.get("protocol", "openai-chat-completions")
        if isinstance(protocol, str):
            data["protocol"] = {
                "openai": "openai-chat-completions",
                "anthropic": "anthropic-messages",
            }.get(protocol, protocol)
        old_model = data.pop("model", None)
        if "models" not in data and isinstance(old_model, str) and old_model.strip():
            data["models"] = [{"id": old_model.strip()}]
        return data

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value: HttpUrl) -> HttpUrl:
        if value.username or value.password:
            raise ValueError("API 地址不能内嵌用户名或密码")
        if value.query or value.fragment:
            raise ValueError("请输入协议根地址，不包含查询参数或片段")
        return value

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        ids = [model.id for model in self.models]
        if len(set(ids)) != len(ids):
            raise ValueError("同一连接中的模型 ID 不能重复")
        self.default_model_id = self.default_model_id.strip()
        if not self.default_model_id and ids:
            self.default_model_id = ids[0]
        if self.default_model_id and self.default_model_id not in ids:
            raise ValueError("默认模型必须在目录中")
        if self.protocol == "anthropic-messages" and any(
            model.reasoning_efforts is not False for model in self.models
        ):
            raise ValueError("Anthropic 协议暂不支持推理档位映射，请显式移除映射")
        return self


class ModelDiscoverRequest(ModelContract):
    config: ModelConfig
    resource_id: StrictStr | None = None
    revision: PositiveInt | None = None
    clear_api_key: StrictBool = False

    @model_validator(mode="after")
    def reference_pair(self) -> Self:
        if (self.resource_id is None) != (self.revision is None):
            raise ValueError("引用已保存凭据时必须同时提供资源 ID 和 revision")
        return self


class ModelProbeRequest(ModelDiscoverRequest):
    model_id: StrictStr | None = None
    reasoning_effort: ReasoningEffort | None = None


class SavedModelProbeRequest(ModelContract):
    revision: PositiveInt
    model_id: StrictStr
    reasoning_effort: ReasoningEffort | None = None


class ModelDiscovery(ModelContract):
    models: list[ModelEntry]


class ModelConnectionFailure(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

    def result(self) -> dict:
        return {"status": "failed", "code": self.code, "message": self.message}
