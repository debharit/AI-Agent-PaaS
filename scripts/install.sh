#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"

export PATH="${HOME}/.local/bin:${PATH}"


# 1. Virtual environment
if [[ ! -x "${VENV_PYTHON}" ]]; then
    echo "==> Creating virtual environment"
    python3 -m venv "${PROJECT_ROOT}/.venv"
fi


# 2. Python packages
echo "==> Installing Python packages"
"${VENV_PYTHON}" -m pip install --upgrade pip
"${VENV_PYTHON}" -m pip install -r "${PROJECT_ROOT}/requirements.txt"


# 3. Antigravity CLI
if command -v agy >/dev/null 2>&1; then
    echo "==> Antigravity CLI already installed"
else
    echo "==> Installing Antigravity CLI"
    curl -fsSL https://antigravity.google/cli/install.sh | bash
    export PATH="${HOME}/.local/bin:${PATH}"
fi


# 4. Login
echo "==> Logging in to Antigravity"
agy


echo
echo "Done. Now run:  python3 app/main.py"