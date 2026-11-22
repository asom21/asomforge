# 提供配置增删改查、启用切换和 Skill 文件列表接口。
from fastapi import APIRouter, HTTPException

from asomforge.application.configurations import ConfigurationService
from asomforge.domain.configurations import KINDS, Draft, EnabledChange, Kind, Resource


def require_kind(value: str) -> Kind:
    if value not in KINDS:
        raise HTTPException(404, "该配置类型暂未开放")
    return value


def resource_router(service: ConfigurationService) -> APIRouter:
    router = APIRouter(prefix="/api/configurations", tags=["configurations"])
    repository = service.repository

    @router.get("/{kind}", response_model=list[Resource])
    def list_resources(kind: str):
        return repository.list(require_kind(kind))

    @router.post("/{kind}", response_model=Resource, status_code=201)
    def create_resource(kind: str, draft: Draft):
        return service.save(require_kind(kind), draft)

    @router.get("/{kind}/{resource_id}", response_model=Resource)
    def get_resource(kind: str, resource_id: str):
        return repository.get(require_kind(kind), resource_id)

    @router.put("/{kind}/{resource_id}", response_model=Resource)
    def update_resource(kind: str, resource_id: str, draft: Draft):
        return service.save(require_kind(kind), draft, resource_id)

    @router.patch("/{kind}/{resource_id}", response_model=Resource)
    def set_enabled(kind: str, resource_id: str, change: EnabledChange):
        return service.set_enabled(require_kind(kind), resource_id, change)

    @router.delete("/{kind}/{resource_id}", status_code=204)
    def delete_resource(kind: str, resource_id: str):
        service.delete(require_kind(kind), resource_id)

    @router.get("/skills/{resource_id}/files")
    def skill_files(resource_id: str):
        return [
            {"path": path, "size": len(content)}
            for path, content in repository.asset_files(resource_id).items()
        ]

    return router
