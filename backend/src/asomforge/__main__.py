# 解析启动参数并运行本机 FastAPI 服务。
import argparse
import logging
import os
from pathlib import Path

import uvicorn

from asomforge.main import create_app


def main():
    parser = argparse.ArgumentParser(description="AsomForge 本地配置中心")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", type=Path, help="本地数据根目录，默认项目 doc/")
    args = parser.parse_args()
    # Transport libraries can include request URLs or protocol input in their diagnostic logs.
    for name in ("mcp", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    uvicorn.run(
        create_app(args.data_dir),
        host="127.0.0.1",
        port=args.port,
        log_level=os.getenv("ASOMFORGE_LOG_LEVEL", "info"),
        access_log=False,
    )


if __name__ == "__main__":
    main()
