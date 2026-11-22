# 解包 Skill 资源并校验清单、大小和文件路径。
import io
import re
import stat
import zipfile
from pathlib import PurePosixPath

from asomforge.domain.configurations import ConfigurationError, skill_manifest


def safe_path(name: str) -> str:
    name = name.replace("\\", "/")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", name):
        raise ConfigurationError("导入文件包含不安全的路径")
    if any(":" in part for part in path.parts):
        raise ConfigurationError("文件路径不能包含冒号")
    return path.as_posix()


def skill_packages(files: dict[str, bytes], size_limit: int) -> list[tuple[dict, dict]]:
    expanded = {}
    unpacked_size = 0
    for name, content in files.items():
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as bundle:
                    unpacked_size += sum(entry.file_size for entry in bundle.infolist())
                    if unpacked_size > size_limit:
                        raise ConfigurationError("解压后的 Skill 超过导入大小限制")
                    for entry in bundle.infolist():
                        relative = safe_path(entry.filename)
                        if stat.S_ISLNK(entry.external_attr >> 16):
                            raise ConfigurationError("Skill 包不能包含符号链接")
                        if not entry.is_dir():
                            if relative in expanded:
                                raise ConfigurationError("Skill 包包含重复文件路径")
                            expanded[relative] = bundle.read(entry)
            except (zipfile.BadZipFile, RuntimeError) as error:
                raise ConfigurationError(
                    "无法读取 Skill ZIP，请使用未加密的标准 ZIP 文件"
                ) from error
        else:
            unpacked_size += len(content)
            if unpacked_size > size_limit:
                raise ConfigurationError("Skill 文件总大小超过导入限制")
            expanded[safe_path(name)] = content
    manifests = [path for path in expanded if PurePosixPath(path).name == "SKILL.md"]
    if not manifests:
        raise ConfigurationError("未找到 SKILL.md，请选择 Skill 目录、ZIP 或 SKILL.md")
    packages = []
    for path in manifests:
        try:
            content = expanded[path].decode("utf-8-sig")
            manifest = skill_manifest(content)
        except (UnicodeError, ValueError) as error:
            raise ConfigurationError(str(error)) from error
        parent = PurePosixPath(path).parent
        assets = {
            str(PurePosixPath(name).relative_to(parent)): value
            for name, value in expanded.items()
            if PurePosixPath(name).is_relative_to(parent)
        }
        if any(name != "SKILL.md" and name.endswith("/SKILL.md") for name in assets):
            raise ConfigurationError("Skill 包不能嵌套另一个 Skill，请分别导入")
        packages.append(
            (
                {
                    "name": manifest["name"],
                    "description": manifest["description"],
                    "config": {"content": content},
                },
                assets,
            )
        )
    return packages
