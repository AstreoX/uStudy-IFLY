"""Code Sandbox Tools - Python code execution in sandboxed subprocess"""

import asyncio
import base64
import json
import logging
import os
import shutil
import tempfile
from typing import Any
from uuid import uuid4

from chat.tools.base import ToolResult
from config import get_settings
from upload.storage import get_storage

logger = logging.getLogger(__name__)

# Path to the runner script (inside Docker: /app/sandbox/_runner.py)
_RUNNER_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sandbox", "_runner.py")

# ============ Tool Definition ============

CODE_SANDBOX_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_python_code",
            "description": (
                "执行 Python 代码并返回结果。用于数学计算、数据分析、算法演示、科学计算、机器学习等。"
                "支持库: numpy, pandas, matplotlib, sympy, scipy, scikit-learn, seaborn, networkx, statsmodels, jieba, wordcloud, Pillow。"
                "matplotlib/seaborn 图表会自动捕获并显示。30秒超时，256MB内存限制。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的 Python 代码",
                    },
                    "description": {
                        "type": "string",
                        "description": "代码功能简述",
                    },
                },
                "required": ["code"],
            },
        },
    },
]

CODE_SANDBOX_TOOL_NAMES: set[str] = {t["function"]["name"] for t in CODE_SANDBOX_TOOLS}


# ============ Executor ============

class CodeSandboxExecutor:
    """Stateless executor for Python code sandbox."""

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if tool_name != "run_python_code":
            return ToolResult(success=False, data=None, message=f"未知的工具: {tool_name}")

        try:
            return await self._run_code(arguments)
        except Exception as e:
            logger.error(f"Code sandbox execution error: {e}", exc_info=True)
            return ToolResult(success=False, data=None, message=f"代码执行失败: {e!s}")

    async def _run_code(self, args: dict[str, Any]) -> ToolResult:
        settings = get_settings()
        code = args.get("code", "")
        description = args.get("description", "")

        if not code.strip():
            return ToolResult(success=False, data=None, message="请提供要执行的代码")

        max_len = settings.code_sandbox_max_code_length
        if len(code) > max_len:
            return ToolResult(
                success=False, data=None,
                message=f"代码长度超限（{len(code)}/{max_len} 字符）",
            )

        sandbox_dir = tempfile.mkdtemp(prefix="sandbox_")
        try:
            # Write user code
            script_path = os.path.join(sandbox_dir, "script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Copy runner script
            runner_dest = os.path.join(sandbox_dir, "_runner.py")
            shutil.copy2(_RUNNER_PATH, runner_dest)

            # Set env vars for resource limits
            env = os.environ.copy()
            env["SANDBOX_MEMORY_MB"] = str(settings.code_sandbox_memory_mb)
            env["SANDBOX_CPU_SECONDS"] = str(settings.code_sandbox_timeout + 5)
            env["SANDBOX_MAX_OUTPUT"] = str(settings.code_sandbox_max_output_length)

            # Execute subprocess
            timeout = settings.code_sandbox_timeout
            process = await asyncio.create_subprocess_exec(
                "python3", "_runner.py",
                cwd=sandbox_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    success=False, data=None,
                    message=f"代码执行超时（{timeout}秒限制）",
                )

            # Parse runner output
            raw_stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
            if not raw_stdout:
                raw_stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
                return ToolResult(
                    success=False, data=None,
                    message=f"执行器异常退出（code={process.returncode}）: {raw_stderr[:500]}",
                )

            try:
                result = json.loads(raw_stdout)
            except json.JSONDecodeError:
                return ToolResult(
                    success=False, data=None,
                    message=f"执行器输出解析失败: {raw_stdout[:300]}",
                )

            # Check for image output
            image_base64 = None
            image_url = None
            output_png = os.path.join(sandbox_dir, "output.png")
            if result.get("has_image") and os.path.exists(output_png):
                with open(output_png, "rb") as f:
                    image_bytes = f.read()
                image_base64 = base64.b64encode(image_bytes).decode("ascii")

                # Save to storage
                filename = f"{uuid4()}.png"
                storage = get_storage()
                image_url = await storage.save(image_bytes, filename, subdir="generated/sandbox")

            has_error = bool(result.get("error"))
            stdout_text = result.get("stdout", "")
            stderr_text = result.get("stderr", "")

            data = {
                "stdout": stdout_text,
                "stderr": stderr_text,
                "description": description,
            }
            if image_url:
                data["image_url"] = image_url

            # Build message for LLM context
            msg_parts = []
            if stdout_text:
                msg_parts.append(f"输出:\n{stdout_text}")
            if stderr_text:
                label = "错误" if has_error else "警告"
                msg_parts.append(f"{label}:\n{stderr_text}")
            if image_url:
                msg_parts.append("已生成图表图片。")
            if not msg_parts:
                msg_parts.append("代码执行完成，无输出。")

            return ToolResult(
                success=not has_error,
                data=data,
                message="\n".join(msg_parts),
                image_base64=image_base64,
            )
        finally:
            shutil.rmtree(sandbox_dir, ignore_errors=True)
