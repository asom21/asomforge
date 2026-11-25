# 定义配置资源、启用状态与检查结果的校验规则。
import re
from datetime import UTC, datetime
from typing import Annotated, Literal, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    StrictStr,
    computed_field,
    model_validator,
)

from asomforge.domain.model_connections import ModelConfig

Kind = Literal["skills", "mcp", "prompts", "models", "platforms"]
KINDS: tuple[Kind, ...] = ("skills", "mcp", "prompts", "models", "platforms")
VARIABLE = re.compile(r"{{\s*([A-Za-z_]\w*)\s*}}")


class ConfigurationError(Exception):
    def __init__(self, message: str, status: int = 422):
        self.message = message
        self.status = status
        super().__init__(message)


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def skill_manifest(content: str) -> dict:
    match = re.match(r"\A---\s*\r?\n(.*?)\r?\n---(?:\s*\r?\n|$)", content, re.S)
    if not match:
        raise ValueError("SKILL.md 必须包含 YAML frontmatter")
    try:
        data = yaml.safe_load(match[1])
    except yaml.YAMLError as error:
        raise ValueError("SKILL.md 的 YAML 格式不正确") from error
    if not isinstance(data, dict):
        raise ValueError("Skill 清单必须是对象")
    name, description = data.get("name"), data.get("description")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("Skill name 必须使用小写字母、数字和单个连字符")
    if len(name) > 64:
        raise ValueError("Skill name 最多 64 个字符")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        raise ValueError("Skill description 必须为 1–1024 个字符的文本")
    return data


class SkillConfig(ConfigModel):
    content: str
    skill_name: str = ""

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        self.skill_name = skill_manifest(self.content)["name"]
        return self


class McpConfig(ConfigModel):
    type: Literal["stdio", "http", "sse"] = "stdio"
    command: StrictStr = ""
    args: list[StrictStr] = Field(default_factory=list)
    env: dict[str, StrictStr] = Field(default_factory=dict)
    cwd: str | None = None
    url: str = ""
    headers: dict[str, StrictStr] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def infer_transport(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if data.get("command") and data.get("url"):
            raise ValueError("command 和 url 不能同时提供，请明确选择连接方式")
        if not data.get("type"):
            data["type"] = "http" if data.get("url") else "stdio"
        return data

    @model_validator(mode="after")
    def check_connection_fields(self) -> Self:
        if self.type == "stdio" and not self.command.strip():
            raise ValueError("stdio 连接需要 command")
        if self.type != "stdio":
            if self.command:
                raise ValueError("HTTP/SSE 连接不使用 command")
            if not self.url.startswith(("http://", "https://")):
                raise ValueError("url 必须是 HTTP 或 HTTPS 地址")
            HttpUrl(self.url)
        return self


class PromptConfig(ConfigModel):
    content: Annotated[str, Field(min_length=1)]
    variables: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_variables(self) -> Self:
        found = list(dict.fromkeys(VARIABLE.findall(self.content)))
        if not self.variables:
            self.variables = found
        if any(not re.fullmatch(r"[A-Za-z_]\w*", name) for name in self.variables):
            raise ValueError("变量名称必须以字母或下划线开头")
        missing = set(found) - set(self.variables)
        if missing:
            raise ValueError("缺少变量声明：" + "、".join(sorted(missing)))
        return self


class PlatformConfig(ConfigModel):
    platform: Literal["codex", "claude", "deepseek_harness"]
    command: str = ""
    args: list[StrictStr] = Field(default_factory=list)
    cwd: str | None = None
    env: dict[str, StrictStr] = Field(default_factory=dict)


CONFIG_MODELS = {
    "skills": SkillConfig,
    "mcp": McpConfig,
    "prompts": PromptConfig,
    "models": ModelConfig,
    "platforms": PlatformConfig,
}


class Draft(ConfigModel):
    name: Annotated[str, Field(min_length=1, max_length=160)]
    description: str = ""
    config: dict
    enabled: StrictBool | None = None
    revision: int | None = None
    clear_secrets: list[str] = Field(default_factory=list)


class EnabledChange(ConfigModel):
    enabled: StrictBool
    revision: Annotated[int, Field(ge=1)]


class CheckResult(ConfigModel):
    status: Literal["passed", "limited", "failed"]
    code: str
    message: str
    resource_id: str
    revision: int
    cwd: str
    checked_at: datetime
    details: dict = Field(default_factory=dict)


class Resource(ConfigModel):
    schema_version: Literal[1] = 1
    id: str
    kind: Kind
    name: str
    description: str = ""
    enabled: bool = True
    revision: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    config: dict
    secret_refs: dict[str, str] = Field(default_factory=dict)
    last_check: CheckResult | None = None
    model_checks: dict[str, CheckResult] = Field(default_factory=dict)

    @computed_field
    @property
    def secret_fields(self) -> list[str]:
        return sorted(self.secret_refs)
