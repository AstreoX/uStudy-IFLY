"""Sandbox runner script — executed as a subprocess inside Docker.

Receives user Python code via script.py in the same directory,
executes it with resource limits, captures stdout/stderr/images,
and outputs structured JSON to stdout.
"""

import io
import json
import os
import resource
import sys
import traceback

# ── Resource limits (Linux only) ──
MEMORY_LIMIT_MB = int(os.environ.get("SANDBOX_MEMORY_MB", 256))
CPU_TIME_LIMIT = int(os.environ.get("SANDBOX_CPU_SECONDS", 35))
MAX_OUTPUT_LENGTH = int(os.environ.get("SANDBOX_MAX_OUTPUT", 5000))
MAX_STDERR_LENGTH = 2000

def _set_resource_limits():
    """Apply resource limits via setrlimit.

    Note: RLIMIT_AS (virtual address space) is NOT used because Python +
    numpy + matplotlib easily exceed 512MB of *virtual* memory even though
    physical RSS is only ~150MB.  Docker container memory limits serve as
    the real memory guard instead.
    """
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_TIME_LIMIT, CPU_TIME_LIMIT))
    # No child processes
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    # Max file write size: 10 MB
    file_limit = 10 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_limit, file_limit))


def _setup_matplotlib():
    """Configure matplotlib for headless rendering and patch plt.show()."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        # Use Noto Sans CJK for Chinese text support
        matplotlib.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "Noto Sans CJK", "DejaVu Sans"]
        matplotlib.rcParams["axes.unicode_minus"] = False
        import matplotlib.pyplot as plt

        _original_show = plt.show
        output_dir = os.getcwd()

        def _patched_show(*args, **kwargs):
            fig = plt.gcf()
            fig.savefig(
                os.path.join(output_dir, "output.png"),
                dpi=150,
                bbox_inches="tight",
                facecolor="white",
            )
            plt.close(fig)

        plt.show = _patched_show
    except ImportError:
        pass


def main():
    # Load heavy libraries BEFORE applying resource limits,
    # because matplotlib/numpy imports alone exceed 256MB.
    _setup_matplotlib()
    _set_resource_limits()

    script_path = os.path.join(os.getcwd(), "script.py")
    if not os.path.exists(script_path):
        json.dump(
            {"stdout": "", "stderr": "script.py not found", "has_image": False, "error": "script.py not found"},
            sys.stdout,
        )
        return

    with open(script_path, "r", encoding="utf-8") as f:
        code = f.read()

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    result = {"stdout": "", "stderr": "", "has_image": False, "error": None}

    old_stdout, old_stderr = sys.stdout, sys.stderr
    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        exec_globals = {"__builtins__": __builtins__, "__name__": "__main__"}
        exec(code, exec_globals)
    except Exception:
        tb = traceback.format_exc()
        stderr_capture.write(tb)
        result["error"] = tb.strip().split("\n")[-1]
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    result["stdout"] = stdout_capture.getvalue()[:MAX_OUTPUT_LENGTH]
    result["stderr"] = stderr_capture.getvalue()[:MAX_STDERR_LENGTH]
    result["has_image"] = os.path.exists(os.path.join(os.getcwd(), "output.png"))

    json.dump(result, old_stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
