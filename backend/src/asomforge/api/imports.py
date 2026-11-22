# 解析导入请求，提供预览与确认保存接口。
from fastapi import APIRouter, Request
from starlette.datastructures import UploadFile

from asomforge.api.configurations import require_kind
from asomforge.api.contracts import ImportPreview, ImportResults
from asomforge.application.imports import ImportService, parse_json
from asomforge.domain.configurations import ConfigurationError


async def read_import_source(
    request: Request, size_limit: int
) -> tuple[str, str, dict[str, bytes]]:
    if "multipart/form-data" in request.headers.get("content-type", ""):
        form = await request.form(max_part_size=size_limit)
        files = {}
        total = 0
        for _, value in form.multi_items():
            if isinstance(value, UploadFile):
                content = await value.read(size_limit + 1)
                total += len(content)
                if total > size_limit:
                    raise ConfigurationError("文件超过导入大小限制", 413)
                filename = value.filename or "import.json"
                if filename in files:
                    raise ConfigurationError("上传文件路径重复")
                files[filename] = content
        return str(form.get("text", "")), str(form.get("policy", "skip")), files

    raw = await request.body()
    if len(raw) > size_limit:
        raise ConfigurationError("内容超过导入大小限制", 413)
    body = parse_json(raw.decode("utf-8-sig"))
    if not isinstance(body, dict) or not isinstance(body.get("text", ""), str):
        raise ConfigurationError("导入请求需要 text 文本字段")
    return body.get("text", ""), body.get("policy", "skip"), {}


def import_router(service: ImportService) -> APIRouter:
    router = APIRouter(prefix="/api/imports")

    @router.post(
        "/{kind}/{action}",
        response_model=ImportPreview | ImportResults,
        response_model_exclude_none=True,
    )
    async def import_resources(kind: str, action: str, request: Request):
        resource_kind = require_kind(kind)
        if action not in ("preview", "commit"):
            raise ConfigurationError("导入操作不存在", 404)
        try:
            text, policy, files = await read_import_source(request, service.size_limit)
            items = service.parse(resource_kind, text, files)
        except UnicodeError as error:
            raise ConfigurationError("文本文件请使用 UTF-8 编码") from error
        if action == "preview":
            return service.preview(resource_kind, items)
        return service.commit(resource_kind, items, policy)

    return router
