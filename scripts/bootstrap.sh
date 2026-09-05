#!/usr/bin/env bash

# Verifies if installs.sh has been run

set -Eeuo pipefail


PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
VENV_PYTHON="${VENV_DIR}/bin/python"
INSTALL_SCRIPT="${PROJECT_ROOT}/scripts/install.sh"


log() {
    printf '[bootstrap] %s\n' "$1"
}


fail() {
    printf '\n[bootstrap] ERROR: %s\n' "$1" >&2
    printf '[bootstrap] Run the installer first:\n\n    bash %s\n\n' \
        "${INSTALL_SCRIPT}" >&2
    exit 1
}


command_exists() {
    command -v "$1" >/dev/null 2>&1
}


export PATH="${HOME}/.local/bin:${PATH}"


log "Project root: ${PROJECT_ROOT}"


# 1. Virtual environment

[[ -x "${VENV_PYTHON}" ]] || fail \
    "Virtual environment was not found at ${VENV_DIR}."

"${VENV_PYTHON}" -c "import sys" >/dev/null 2>&1 || fail \
    "Virtual environment at ${VENV_DIR} is broken."


# 2. Python dependencies


"${VENV_PYTHON}" - <<'PY' || fail "Python dependencies are missing or broken."
import sys

import gradio

print(f"[bootstrap] Python executable: {sys.executable}")
print(f"[bootstrap] Gradio version: {gradio.__version__}")
PY


# 3. Antigravity CLI

command_exists agy || fail "'agy' is not on PATH."

log "Antigravity executable: $(command -v agy)"


# 4. Antigravity login Check
# Check if AGY has been authenticated

logged_in="unknown"

for config_dir in \
    "${HOME}/.antigravity" \
    "${HOME}/.config/antigravity" \
    "${HOME}/.agy"
do
    if [[ -d "${config_dir}" ]]; then
        logged_in="likely"
        break
    fi
done

if [[ "${logged_in}" == "likely" ]]; then
    log "Antigravity credentials directory found."
else
    log "WARNING: no Antigravity credentials found. If prompts fail, run: agy login"
fi


log "Preflight checks passed."
