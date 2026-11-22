# 编排各类配置检查，控制超时、并发及结果保存。
import asyncio
import posixpath
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx

from asomforge.application.configurations import ConfigurationService
from asomforge.domain.configurations import ConfigurationError, Resource
from asomforge.runtimes.mcp import check_mcp
from asomforge.runtimes.platforms import check_platform


async def check_model(config: dict, timeout: float) -> dict:
    url = config["base_url"].rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {config['api_key']}"} if config["api_key"] else {}
    if config["protocol"] == "anthropic":
        headers = {"anthropic-version": "2023-06-01", "x-api-key": config["api_key"]}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        response = await client.get(url, headers=headers)
    if response.status_code in (401, 403):
        return {"status": "failed", "code": "auth", "message": "端点拒绝认证，请检查凭据与权限"}
    if response.status_code in (404, 405, 501):
        return {
            "status": "limited",
            "code": "discovery_unsupported",
            "message": "端点不支持模型列表发现，认证和推理能力未验证",
        }
    response.raise_for_status()
    try:
        data = response.json()["data"]
        if not isinstance(data, list):
            raise ValueError
        ids = [item["id"] for item in data if isinstance(item, dict) and "id" in item]
    except (ValueError, KeyError, TypeError):
        return {
            "status": "failed",
            "code": "invalid_response",
            "message": "端点未返回协议要求的模型列表",
        }
    selected = config["model"]
    if selected and selected not in ids:
        return {
            "status": "limited",
            "code": "model_not_listed",
            "details": {"models": len(ids)},
            "message": "模型列表读取成功，但未找到指定模型；未验证推理调用",
        }
    return {
        "status": "passed",
        "code": "discovered",
        "details": {"models": len(ids)},
        "message": "模型列表读取成功；未发送生成请求",
    }


def skill_references(content: str, files: dict) -> list[str]:
    missing = []
    for target in re.findall(r"\]\(([^)\s]+)(?:\s+[^)]*)?\)", content):
        path = unquote(urlsplit(target).path)
        if urlsplit(target).scheme or not path or path.startswith("/"):
            continue
        if posixpath.normpath(path) not in files:
            missing.append(path)
    return missing


def exception_leaves(error: BaseException):
    if isinstance(error, BaseExceptionGroup):
        for child in error.exceptions:
            yield from exception_leaves(child)
    else:
        yield error


class CheckService:
    def __init__(self, service: ConfigurationService, root: Path, timeout: float, concurrency: int):
        if timeout <= 0 or concurrency <= 0:
            raise ValueError("检查超时和并发上限必须为正数")
        self.service = service
        self.root = root
        self.timeout = timeout
        self.slots = asyncio.Semaphore(concurrency)

    async def run(self, resource: Resource) -> dict:
        cwd = Path(resource.config.get("cwd") or self.root).expanduser()
        if not cwd.is_absolute():
            cwd = self.root / cwd
        cwd = str(cwd.resolve())
        metadata = {
            "resource_id": resource.id,
            "revision": resource.revision,
            "cwd": cwd,
            "checked_at": datetime.now(UTC).isoformat(),
        }
        try:
            async with asyncio.timeout(self.timeout), self.slots:
                config = self.service.resolved(resource)
                if not Path(cwd).is_dir():
                    raise ConfigurationError("工作目录不存在或不是目录")
                self.service.validate(resource.kind, config)
                if resource.kind == "mcp":
                    result = await check_mcp(config, cwd, self.timeout)
                elif resource.kind == "models":
                    result = await check_model(config, self.timeout)
                elif resource.kind == "platforms":
                    result = await check_platform(config, cwd)
                elif resource.kind == "skills":
                    missing = skill_references(
                        config["content"], self.service.repository.asset_files(resource.id)
                    )
                    result = {
                        "status": "limited" if missing else "passed",
                        "code": "structure",
                        "message": "存在未找到的相对文件引用"
                        if missing
                        else "Skill 清单、文件结构与相对引用检查通过",
                        "details": {"missing_references": missing},
                    }
                else:
                    result = {
                        "status": "passed",
                        "code": "structure",
                        "message": "Prompt 正文与变量声明检查通过",
                    }
        except (TimeoutError, httpx.TimeoutException):
            result = {
                "status": "failed",
                "code": "timeout",
                "message": "检查超时，已关闭本次连接与进程",
            }
        except FileNotFoundError:
            result = {
                "status": "failed",
                "code": "not_installed",
                "message": "未安装程序或命令路径不可用",
            }
        except ConfigurationError as error:
            result = {"status": "failed", "code": "configuration", "message": error.message}
        except Exception as error:
            # Transport and child-process exceptions may contain credentials or raw output.
            result = {
                "status": "failed",
                "code": "connection",
                "message": "连接或协议检查失败，请核对地址、传输类型和程序配置",
            }
            if any(
                isinstance(item, httpx.HTTPStatusError) and item.response.status_code in (401, 403)
                for item in exception_leaves(error)
            ):
                result = {
                    "status": "failed",
                    "code": "auth",
                    "message": "服务拒绝认证，请检查凭据与权限",
                }
        result.update(metadata)
        self.service.record_check(resource, result)
        return result
