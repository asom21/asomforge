# 组装 FastAPI 应用、配置路由和本地静态页面。
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from asomforge.api.checks import check_router
from asomforge.api.configurations import resource_router
from asomforge.api.contracts import Catalog
from asomforge.api.imports import import_router
from asomforge.api.model_connections import model_connection_router
from asomforge.application.configurations import ConfigurationService
from asomforge.application.imports import ImportService
from asomforge.application.model_connections import ModelConnectionService
from asomforge.domain.configurations import KINDS, ConfigurationError
from asomforge.infrastructure.files import FileRepository
from asomforge.runtimes.checks import CheckService


def create_app(data_dir: Path | None = None) -> FastAPI:
    project_root = Path(__file__).resolve().parents[3]
    root = data_dir or Path(os.getenv("ASOMFORGE_DATA_DIR", str(project_root / "doc")))
    repository = FileRepository(root)
    service = ConfigurationService(repository)
    checks = CheckService(
        service,
        root=repository.root,
        timeout=float(os.getenv("ASOMFORGE_CHECK_TIMEOUT", "20")),
        concurrency=int(os.getenv("ASOMFORGE_CHECK_CONCURRENCY", "3")),
    )
    imports = ImportService(
        service,
        size_limit=int(os.getenv("ASOMFORGE_IMPORT_LIMIT", str(16 * 1024 * 1024))),
    )
    app = FastAPI(title="AsomForge", version="0.1.0")
    app.state.service = service

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        allowed = {"127.0.0.1", "localhost", "::1"}
        origin = request.headers.get("origin")
        if request.url.hostname not in allowed or (
            origin and urlsplit(origin).hostname not in allowed
        ):
            return JSONResponse({"detail": "仅接受本机界面请求"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(ConfigurationError)
    async def configuration_error(request: Request, error: ConfigurationError):
        return JSONResponse({"detail": error.message}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def input_error(request: Request, error: RequestValidationError):
        details = [{"loc": item["loc"], "msg": item["msg"]} for item in error.errors()]
        return JSONResponse({"detail": details}, status_code=422)

    @app.exception_handler(OSError)
    async def filesystem_error(request: Request, error: OSError):
        return JSONResponse({"detail": "文件读写失败，请检查数据目录的访问权限"}, status_code=500)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/catalog", response_model=Catalog)
    def catalog():
        return {
            "data_directory": str(repository.root),
            "counts": {kind: len(repository.list(kind)) for kind in KINDS},
            "platforms": ["codex", "claude", "deepseek_harness"],
        }

    app.include_router(resource_router(service))
    app.include_router(check_router(checks))
    app.include_router(model_connection_router(ModelConnectionService(checks)))
    app.include_router(import_router(imports))
    frontend = project_root / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app
