# 导出后端 OpenAPI 文档，供前端生成接口类型。
import json
import tempfile
from pathlib import Path

from asomforge.main import create_app


def main():
    with tempfile.TemporaryDirectory() as directory:
        schema = create_app(Path(directory)).openapi()
    Path("openapi.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )


if __name__ == "__main__":
    main()
