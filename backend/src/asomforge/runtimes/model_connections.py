# 适配三种模型 HTTP 协议，限制响应大小并返回脱敏的发现与生成结果。
import json

import httpx

from asomforge.domain.model_connections import (
    ModelConfig,
    ModelConnectionFailure,
    ModelEntry,
)

TEST_PROMPT = "请只回复：连接成功。不要执行命令或修改文件。"
RESPONSE_LIMIT = 4 * 1024 * 1024


def endpoint(config: ModelConfig, operation: str) -> str:
    base = str(config.base_url).rstrip("/")
    if config.protocol == "anthropic-messages" and not base.endswith("/v1"):
        base += "/v1"
    return base + "/" + operation


def auth_headers(config: ModelConfig) -> dict[str, str]:
    if config.protocol == "anthropic-messages":
        headers = {"anthropic-version": "2023-06-01"}
        if config.api_key:
            headers["x-api-key"] = config.api_key
        return headers
    return {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}


def http_failure(status: int, body: bytes) -> ModelConnectionFailure:
    if status in (401, 403):
        return ModelConnectionFailure("auth", "端点拒绝认证，请检查 API Key 与访问权限")
    if status == 429:
        return ModelConnectionFailure("rate_limit", "端点限流或额度不足，请检查额度并稍后手动重试")
    if status in (400, 404):
        try:
            error = json.loads(body).get("error", {})
            code = error.get("code") or error.get("type") if isinstance(error, dict) else None
        except (ValueError, AttributeError, RecursionError):
            code = None
        if code in ("model_not_found", "unknown_model", "invalid_model", "model_not_available"):
            return ModelConnectionFailure(
                "model", "端点未找到指定模型或无权使用，请核对模型 ID 与权限"
            )
    if status in (400, 422):
        return ModelConnectionFailure(
            "parameters", "端点不接受请求参数，请检查输出 token 字段、预算或推理档位；未自动重试"
        )
    if 300 <= status < 400 or status in (404, 405, 415, 501):
        return ModelConnectionFailure(
            "protocol", "端点路径或协议不匹配，请核对协议根地址；不跟随重定向"
        )
    return ModelConnectionFailure("provider", "模型服务返回异常状态，请检查服务可用性后手动重试")


async def request_json(
    config: ModelConfig, method: str, operation: str, timeout: float, payload: dict | None = None
):
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            async with client.stream(
                method, endpoint(config, operation), headers=auth_headers(config), json=payload
            ) as response:
                body = bytearray()
                # aiter_bytes yields decompressed bytes; Content-Length cannot enforce this limit.
                async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                    if len(body) + len(chunk) > RESPONSE_LIMIT:
                        raise ModelConnectionFailure(
                            "response_too_large", "端点响应超过解压后 4MiB 上限，已关闭连接"
                        )
                    body.extend(chunk)
                if not 200 <= response.status_code < 300:
                    raise http_failure(response.status_code, bytes(body))
        try:
            data = json.loads(body)
        except (ValueError, UnicodeError, RecursionError) as error:
            raise ModelConnectionFailure("protocol", "端点未返回合法的协议 JSON 响应") from error
        if not isinstance(data, dict):
            raise ModelConnectionFailure("protocol", "端点响应必须是协议 JSON 对象")
        return data
    except httpx.TimeoutException as error:
        raise ModelConnectionFailure("timeout", "模型请求超时，已关闭本次连接") from error
    except httpx.DecodingError as error:
        raise ModelConnectionFailure("protocol", "端点响应压缩或编码无效") from error
    except httpx.RequestError as error:
        raise ModelConnectionFailure(
            "network", "无法连接模型服务，请检查地址、DNS、TLS 和网络连接"
        ) from error
    except (ValueError, UnicodeError) as error:
        raise ModelConnectionFailure(
            "parameters", "请求地址或凭据格式无效，请核对连接配置"
        ) from error


def discovery_entries(data: dict) -> list[ModelEntry]:
    candidates = data.get("data", data.get("models"))
    if isinstance(candidates, dict):
        candidates = [
            {**(value if isinstance(value, dict) else {}), "id": key}
            for key, value in candidates.items()
        ]
    if not isinstance(candidates, list):
        raise ModelConnectionFailure("protocol", "端点不支持标准模型列表发现，可手动配置模型并测试")
    models = []
    seen = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        model_id = candidate.get("id")
        if not isinstance(model_id, str) or not model_id.strip() or model_id.strip() in seen:
            continue
        values = {"id": model_id.strip()}
        name = candidate.get("name", candidate.get("display_name"))
        if isinstance(name, str) and name.strip():
            values["name"] = name
        for field in ("context_window", "max_output_tokens"):
            capacity = candidate.get(field)
            if type(capacity) is int and capacity > 0:
                values[field] = capacity
        if values.get("max_output_tokens", 0) > values.get("context_window", float("inf")):
            values.pop("max_output_tokens", None)
        modalities = candidate.get("input_modalities")
        if isinstance(modalities, list) and modalities:
            valid = list(dict.fromkeys(item for item in modalities if item in ("text", "image")))
            if valid:
                values["input_modalities"] = valid
        models.append(ModelEntry.model_validate(values))
        seen.add(values["id"])
    return models


async def discover_models(config: ModelConfig, timeout: float) -> list[ModelEntry]:
    models = discovery_entries(await request_json(config, "GET", "models", timeout))
    if not config.api_key:
        return models
    safe_models = []
    for model in models:
        if config.api_key in model.id:
            continue
        if model.name:
            model.name = model.name.replace(config.api_key, "[已隐藏凭据]")
        safe_models.append(model)
    return safe_models


def generation_payload(
    config: ModelConfig, model: ModelEntry, reasoning_effort: str | None
) -> tuple[str, dict]:
    budget = min(model.max_output_tokens or 1024, 1024)
    payload = {"model": model.id}
    effort = (
        model.reasoning_efforts.get(reasoning_effort)
        if reasoning_effort and isinstance(model.reasoning_efforts, dict)
        else None
    )
    if config.protocol == "openai-responses":
        operation = "responses"
        payload.update(input=[{"role": "user", "content": TEST_PROMPT}], max_output_tokens=budget)
        if effort is not None:
            payload["reasoning"] = {"effort": effort}
    else:
        payload["messages"] = [{"role": "user", "content": TEST_PROMPT}]
        if config.protocol == "anthropic-messages":
            operation = "messages"
            payload["max_tokens"] = budget
        else:
            operation = "chat/completions"
            payload[config.output_token_field] = budget
            if effort is not None:
                payload["reasoning_effort"] = effort
    return operation, payload


def generation_text(protocol: str, data: dict) -> tuple[str, bool, bool]:
    try:
        if protocol == "openai-chat-completions":
            choices = data["choices"]
            if not isinstance(choices, list):
                raise ValueError
            if not choices:
                return "", False, False
            choice = choices[0]
            message = choice["message"]
            text = message.get("content")
            if text is None:
                text = ""
            if not isinstance(text, str):
                raise ValueError
            tools = bool(message.get("tool_calls") or message.get("function_call"))
            return text, tools, choice.get("finish_reason") == "length"
        if protocol == "openai-responses":
            if "status" in data and data["status"] not in ("completed", "incomplete"):
                raise ModelConnectionFailure(
                    "protocol", "Responses 请求未成功完成，请检查端点协议和服务状态"
                )
            output = data["output"]
            if not isinstance(output, list):
                raise ValueError
            text, tools = [], False
            for item in output:
                if item.get("type") == "message":
                    for part in item["content"]:
                        if part.get("type") == "output_text":
                            if not isinstance(part["text"], str):
                                raise ValueError
                            text.append(part["text"])
                elif item.get("type", "").endswith("_call"):
                    tools = True
            return "".join(text), tools, data.get("status") == "incomplete"
        blocks = data["content"]
        if not isinstance(blocks, list):
            raise ValueError
        text, tools = [], False
        for block in blocks:
            if block.get("type") == "text":
                if not isinstance(block["text"], str):
                    raise ValueError
                text.append(block["text"])
            if block.get("type") == "tool_use":
                tools = True
        return "".join(text), tools, data.get("stop_reason") == "max_tokens"
    except (KeyError, ValueError, TypeError, AttributeError, IndexError) as error:
        raise ModelConnectionFailure(
            "protocol", "端点响应不符合所选生成协议，请核对地址和协议"
        ) from error


async def generate_text(
    config: ModelConfig, model: ModelEntry, reasoning_effort: str | None, timeout: float
) -> dict:
    operation, payload = generation_payload(config, model, reasoning_effort)
    data = await request_json(config, "POST", operation, timeout, payload)
    text, tools, truncated = generation_text(config.protocol, data)
    preview = text.strip()
    if config.api_key:
        preview = preview.replace(config.api_key, "[已隐藏凭据]")
    details = {"response_preview": preview[:240]} if preview else {}
    if tools:
        status, code, message = (
            "limited",
            "tool_response",
            "收到工具调用响应，本次未确认文本回复；不会执行工具",
        )
    elif truncated:
        status, code, message = "limited", "output_limit", "本次输出预算耗尽，未确认完整文本回复"
    elif not text.strip():
        status, code, message = "limited", "empty_response", "端点返回空响应，本次未确认文本回复"
    elif text.strip().rstrip("。.").strip() == "连接成功":
        status, code, message = "passed", "generation", "模型按约定回复连接成功，文本连通性测试通过"
    else:
        status, code, message = (
            "limited",
            "unexpected_text",
            "已收到模型回复，但未按约定返回连接成功",
        )
    return {"status": status, "code": code, "message": message, "details": details}
