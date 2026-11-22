# 提供用于握手和能力发现验证的受控 MCP 测试服务。
import argparse

from mcp.server.fastmcp import FastMCP

server = FastMCP("controlled-probe")


@server.tool()
def never_call() -> str:
    raise RuntimeError("Connectivity checks must not call tools")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", default="stdio")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server.settings.port = args.port
    server.run(transport=args.transport)
