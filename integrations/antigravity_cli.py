"""
Thin wrapper around the Antigravity CLI (`agy`).
"""

import shutil
import subprocess
from pathlib import Path
from typing import Optional


class AntigravityError(RuntimeError):
    """Raised when an `agy` call cannot be made or fails."""


def run_antigravity(
    prompt: str,
    workspace: Optional[Path] = None,
    timeout_seconds: float = 90,
) -> str:

    prompt = prompt.strip()
    if not prompt:
        raise AntigravityError("The Antigravity prompt cannot be empty.")

    if shutil.which("agy") is None:
        raise AntigravityError("The 'agy' executable was not found in PATH.")

    try:
        result = subprocess.run(
            ["agy", "--print", prompt],
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise AntigravityError(f"Antigravity timed out after {timeout_seconds} seconds.")
    except OSError as exc:
        raise AntigravityError(f"Failed to start Antigravity: {exc}")

    if result.returncode != 0:
        raise AntigravityError(
            result.stderr.strip() or f"Antigravity exited with code {result.returncode}."
        )

    response = result.stdout.strip()
    if not response:
        raise AntigravityError("Antigravity returned an empty response.")

    return response
