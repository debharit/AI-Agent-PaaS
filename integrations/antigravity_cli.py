import subprocess


def run_antigravity(prompt: str, timeout_seconds: float = 90) -> str:
    result = subprocess.run(
        ["agy", "--print", prompt],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )

    return (result.stdout or "").strip()
