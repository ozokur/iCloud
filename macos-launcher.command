#!/bin/bash
set -euo pipefail

if [[ "$(uname)" != "Darwin" ]]; then
  echo "This launcher is intended for macOS. Detected: $(uname)."
  exit 1
fi

export PIP_DISABLE_PIP_VERSION_CHECK=1
VERBOSE=${VERBOSE:-0}

# Parse command line args for verbose mode
for arg in "$@"; do
  if [[ "$arg" == "--verbose" || "$arg" == "-v" ]]; then
    VERBOSE=1
    echo "[icloud-helper] Verbose mode enabled"
  fi
done
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

echo "[icloud-helper] Checking dependencies..."

# Check if icloud-multi-agent is installed and up to date
INSTALLED_VERSION=$(python -c "from icloud_multi_agent import __version__; print(__version__)" 2>/dev/null || echo "none")
PROJECT_VERSION=$(grep "^version = " "$PROJECT_ROOT/pyproject.toml" | cut -d'"' -f2)

if [[ "$INSTALLED_VERSION" != "$PROJECT_VERSION" ]]; then
  echo "  → Version mismatch (installed: $INSTALLED_VERSION, expected: $PROJECT_VERSION)"
  echo "  → Updating dependencies (this may take 30-60 seconds on first run)..."
  
  if [[ $VERBOSE -eq 1 ]]; then
    python -m pip install --upgrade pip setuptools wheel --timeout 60 || {
      echo "  ⚠️  Warning: pip upgrade failed, continuing anyway..."
    }
    echo "  → Installing icloud-multi-agent and icloudpy..."
    python -m pip install -e "$PROJECT_ROOT" --timeout 120 || {
      echo "  ❌ Error: Installation failed. Check your internet connection."
      read -r -p "Press Enter to close..." _
      exit 1
    }
  else
    python -m pip install --upgrade pip setuptools wheel --timeout 60 --quiet || {
      echo "  ⚠️  Warning: pip upgrade failed, continuing anyway..."
    }
    echo "  → Installing icloud-multi-agent and icloudpy..."
    python -m pip install -e "$PROJECT_ROOT" --timeout 120 --quiet || {
      echo "  ❌ Error: Installation failed. Check your internet connection."
      read -r -p "Press Enter to close..." _
      exit 1
    }
  fi
  
  echo "  ✅ Updated to version $PROJECT_VERSION"
else
  echo "  ✅ Already up to date (v$INSTALLED_VERSION)"
fi

echo "[icloud-helper] Launching GUI..."
python -m icloud_multi_agent.gui "$@"

EXIT_CODE=$?
if [[ $EXIT_CODE -ne 0 ]]; then
  echo "[icloud-helper] GUI exited with status $EXIT_CODE"
fi

read -r -p "Press Enter to close this window..." _
exit $EXIT_CODE
