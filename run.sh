#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
VENV_DIR="${ALIENFX_STUDIO_VENV:-$PROJECT_DIR/.venv}"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    python3 -m venv "$VENV_DIR"
fi

if [[ ! -f "$VENV_DIR/.studio-deps-installed" || "$PROJECT_DIR/requirements.txt" -nt "$VENV_DIR/.studio-deps-installed" ]]; then
    "$VENV_DIR/bin/python" -m pip install -r "$PROJECT_DIR/requirements.txt"
    touch "$VENV_DIR/.studio-deps-installed"
fi

if [[ $# -eq 0 ]] && "$VENV_DIR/bin/python" -c 'import urllib.request; response=urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=1); response.close()' >/dev/null 2>&1; then
    printf 'AlienFX Studio is already running; opening the existing session.\n'
    "$VENV_DIR/bin/python" -c 'import webbrowser; webbrowser.open("http://127.0.0.1:8765")' >/dev/null 2>&1 || true
    exit 0
fi

cd "$PROJECT_DIR"
exec "$VENV_DIR/bin/python" -m alienfx_studio "$@"
