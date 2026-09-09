"""
Runs agent-generated code in a network-disabled, resource-capped Docker
container. This is the "coding task run and verified in a sandbox" demo piece.
Requires: Docker installed, and images pulled ahead of time (python:3.11-slim).
"""
import tempfile
import uuid
from pathlib import Path
import docker

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


IMAGE_BY_LANG = {
    "python": "python:3.11-slim",
    "bash": "python:3.11-slim",   # slim image has /bin/sh; good enough for simple shell checks
}

RUN_CMD_BY_LANG = {
    "python": lambda fname: ["python", fname],
    "bash": lambda fname: ["sh", fname],
}


def run_code(code: str, language: str = "python", timeout_seconds: int = 20) -> dict:
    """
    Returns: {"stdout": str, "stderr": str, "exit_code": int, "timed_out": bool}
    """
    if language not in IMAGE_BY_LANG:
        return {"stdout": "", "stderr": f"Unsupported language: {language}", "exit_code": 1, "timed_out": False}

    client = _get_client()
    workdir = Path(tempfile.mkdtemp(prefix="sandbox_"))
    fname = "snippet.py" if language == "python" else "snippet.sh"
    (workdir / fname).write_text(code)

    container = None
    try:
        container = client.containers.run(
            image=IMAGE_BY_LANG[language],
            command=RUN_CMD_BY_LANG[language](f"/work/{fname}"),
            volumes={str(workdir): {"bind": "/work", "mode": "ro"}},
            working_dir="/work",
            network_disabled=True,          # <-- the air-gap guarantee, per-container too
            mem_limit="512m",
            nano_cpus=1_000_000_000,        # 1 CPU
            detach=True,
            stdout=True,
            stderr=True,
        )
        result = container.wait(timeout=timeout_seconds)
        logs = container.logs(stdout=True, stderr=False).decode(errors="replace")
        errs = container.logs(stdout=False, stderr=True).decode(errors="replace")
        return {
            "stdout": logs,
            "stderr": errs,
            "exit_code": result.get("StatusCode", 1),
            "timed_out": False,
        }
    except Exception as e:
        return {"stdout": "", "stderr": f"Sandbox error or timeout: {e}", "exit_code": 1, "timed_out": True}
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass
