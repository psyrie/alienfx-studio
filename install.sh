#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$DATA_HOME/alienfx-studio/app"
APPLICATIONS_DIR="$DATA_HOME/applications"
DESKTOP_FILE="$APPLICATIONS_DIR/alienfx-studio.desktop"
LEGACY_DESKTOP_FILE="$APPLICATIONS_DIR/alienfx.desktop"
ICON_48_DIR="$DATA_HOME/icons/hicolor/48x48/apps"
ICON_SCALABLE_DIR="$DATA_HOME/icons/hicolor/scalable/apps"

mkdir -p "$APP_DIR" "$APPLICATIONS_DIR" "$ICON_48_DIR" "$ICON_SCALABLE_DIR"
tar -C "$SOURCE_DIR" \
    --exclude=.git \
    --exclude=.venv \
    --exclude=__pycache__ \
    --exclude='*.py[cod]' \
    --exclude=.pytest_cache \
    --exclude=build \
    --exclude=dist \
    --exclude='*.egg-info' \
    -cf - . | tar -C "$APP_DIR" -xf -

if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
    python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
touch "$APP_DIR/.venv/.studio-deps-installed"
install -m 644 "$APP_DIR/alienfx/data/icons/hicolor/48x48/apps/alienfx.png" "$ICON_48_DIR/alienfx-studio.png"
install -m 644 "$APP_DIR/alienfx/data/icons/hicolor/scalable/apps/alienfx.svg" "$ICON_SCALABLE_DIR/alienfx-studio.svg"

DESKTOP_TEMP="$(mktemp "$APPLICATIONS_DIR/.alienfx-studio.XXXXXX")"
trap 'rm -f "$DESKTOP_TEMP"' EXIT
printf '[Desktop Entry]\nVersion=1.0\nType=Application\nName=AlienFX Studio\nComment=Configure AlienFX lighting\nExec="%s/run.sh"\nTryExec=%s/run.sh\nIcon=alienfx-studio\nTerminal=false\nStartupNotify=true\nCategories=Utility;\nKeywords=Alienware;Lighting;AlienFX;\n' \
    "$APP_DIR" "$APP_DIR" > "$DESKTOP_TEMP"
install -m 644 "$DESKTOP_TEMP" "$DESKTOP_FILE"
if [[ -f "$LEGACY_DESKTOP_FILE" ]] && grep -Fqx 'Comment=AlienFX lighting studio' "$LEGACY_DESKTOP_FILE"; then
    rm -f "$LEGACY_DESKTOP_FILE"
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1 \
    && [[ -f "$DATA_HOME/icons/hicolor/index.theme" ]]; then
    gtk-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

printf 'AlienFX Studio installed for this user. Launch it from the applications menu.\n'
printf 'Use the Quit button in Studio to stop its local server.\n'
printf 'To uninstall, run: %s/uninstall.sh\n' "$APP_DIR"