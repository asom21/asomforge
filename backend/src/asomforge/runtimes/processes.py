# 解析跨平台启动命令，管理检查子进程的输出与清理。
import asyncio
import os
import shutil
import signal
import subprocess
from pathlib import Path

from asomforge.domain.configurations import ConfigurationError


def executable(command: str, cwd: str, env: dict) -> str:
    path = Path(command).expanduser()
    if path.is_absolute() or path.parent != Path("."):
        resolved = path if path.is_absolute() else Path(cwd) / path
        if resolved.is_file():
            return str(resolved.resolve())
    found = shutil.which(command, path=env.get("PATH", os.environ.get("PATH")))
    if not found:
        raise FileNotFoundError(command)
    return found


def launch_arguments(arguments: list[str], cwd: str, env: dict) -> list[str]:
    command, *args = arguments
    program = executable(command, cwd, env)
    suffix = Path(program).suffix.lower()
    if os.name == "nt" and suffix == ".ps1":
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", program, *args]
    if os.name == "nt" and suffix in (".cmd", ".bat"):
        # Batch wrappers require cmd.exe; keep parameters from becoming shell syntax.
        if any(any(char in arg for char in "&|<>^%!\r\n") for arg in [program, *args]):
            raise ConfigurationError(
                "Windows 批处理命令参数含 shell 特殊字符，请改用可执行程序路径"
            )
    return [program, *args]


async def run_process(arguments: list[str], cwd: str, env: dict) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(
        *launch_arguments(arguments, cwd, env),
        cwd=cwd,
        env={**os.environ, **env},
        stdin=subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=os.name != "nt",
    )
    try:
        output, _ = await process.communicate()
        return process.returncode, output[:16384].decode("utf-8", errors="replace")
    finally:
        if process.returncode is None:
            if os.name == "nt":
                await asyncio.to_thread(
                    subprocess.run,
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            await process.wait()
