#!/bin/bash
set -euo pipefail

if [[ "$(uname)" != "Darwin" ]]; then
  echo "This launcher is intended for macOS. Detected: $(uname)."
  exit 1
fi

export PIP_DISABLE_PIP_VERSION_CHECK=1
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
VENV_DIR="$PROJECT_ROOT/.venv_macos"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  fi
fi

if [[ -z "$PYTHON_BIN" ]]; then
  cat <<'MSG'
[icloud-helper] python3 (3.11+) not found.
Install it from https://www.python.org/downloads/mac-osx/ and rerun this launcher.
MSG
  read -r -p "Press Enter to close..." _
  exit 1
fi

mkdir -p "$VENV_DIR"
if [[ ! -d "$VENV_DIR/bin" ]]; then
  echo "[icloud-helper] Creating virtual environment at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "[icloud-helper] Ensuring dependencies are installed..."
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e "$PROJECT_ROOT"

echo "[icloud-helper] Launching GUI..."
python -m icloud_multi_agent.gui "$@"

EXIT_CODE=$?
if [[ $EXIT_CODE -ne 0 ]]; then
  echo "[icloud-helper] GUI exited with status $EXIT_CODE"
fi

read -r -p "Press Enter to close this window..." _
exit $EXIT_CODE
