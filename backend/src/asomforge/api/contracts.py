# 定义配置目录和导入结果的 HTTP 响应结构。
from typing import Literal

from pydantic import BaseModel

from asomforge.domain.configurations import Kind


class Catalog(BaseModel):
    data_directory: str
    counts: dict[Kind, int]
    platforms: list[str]


class ImportPreviewItem(BaseModel):
    name: str
    warnings: list[str]
    error: str | None = None
    conflict: str | None = None
    files: list[str]


class ImportPreview(BaseModel):
    items: list[ImportPreviewItem]


class ImportOutcome(BaseModel):
    name: str
    status: Literal["saved", "skipped", "failed"]
    id: str | None = None
    error: str | None = None
    warning: str | None = None


class ImportResults(BaseModel):
    results: list[ImportOutcome]
