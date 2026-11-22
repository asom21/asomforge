# 检查本机运行平台的版本及其支持的只读认证状态。
import json
import re

from asomforge.runtimes.processes import run_process

PLATFORM_COMMANDS = {"codex": "codex", "claude": "claude", "deepseek_harness": "dsh"}


async def check_platform(config: dict, cwd: str) -> dict:
    platform = config["platform"]
    base = [config["command"] or PLATFORM_COMMANDS[platform], *config["args"]]
    code, output = await run_process([*base, "--version"], cwd, config["env"])
    version = re.search(r"\b\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9.]+)?\b", output)
    if code != 0 or not version:
        return {
            "status": "failed",
            "code": "version",
            "message": "程序未返回可识别的版本，请检查命令和参数",
        }
    details = {"version": version.group(), "installation": "available"}
    if platform == "deepseek_harness":
        return {
            "status": "limited",
            "code": "auth_unverified",
            "details": details,
            "message": "程序与版本已确认；Harness 认证状态尚未验证，本次未启动任务",
        }
    args = ["login", "status"] if platform == "codex" else ["auth", "status", "--json"]
    code, output = await run_process([*base, *args], cwd, config["env"])
    if platform == "claude":
        try:
            logged_in = json.loads(output).get("loggedIn")
        except (ValueError, AttributeError):
            logged_in = None
    else:
        logged_in = True if code == 0 else False if "not logged in" in output.lower() else None
    if logged_in is False:
        return {
            "status": "failed",
            "code": "auth",
            "details": details,
            "message": "程序已安装，尚未认证；请在对应平台中完成登录或设置凭据",
        }
    if logged_in is None:
        return {
            "status": "limited",
            "code": "auth_unverified",
            "details": details,
            "message": "程序与版本已确认；当前版本未返回可识别的认证状态",
        }
    return {
        "status": "passed",
        "code": "available",
        "details": details,
        "message": "程序、版本和已有认证状态已确认；未执行 Agent 任务",
    }
