#!/usr/bin/env bash
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_ROOT="$DATA_HOME/alienfx-studio"
APP_DIR="$APP_ROOT/app"
DESKTOP_FILE="$DATA_HOME/applications/alienfx-studio.desktop"
LEGACY_DESKTOP_FILE="$DATA_HOME/applications/alienfx.desktop"
ICON_48_FILE="$DATA_HOME/icons/hicolor/48x48/apps/alienfx-studio.png"
ICON_SCALABLE_FILE="$DATA_HOME/icons/hicolor/scalable/apps/alienfx-studio.svg"

if [[ "${1:-}" != "--yes" ]]; then
    if [[ ! -t 0 ]]; then
        printf 'Run this script in a terminal or pass --yes to confirm removal.\n' >&2
        exit 1
    fi
    printf 'Remove AlienFX Studio and its launcher? Saved palettes in ~/.config will be kept. [y/N] '
    read -r answer
    [[ "$answer" == [yY] || "$answer" == [yY][eE][sS] ]] || exit 0
fi

rm -f "$DESKTOP_FILE"
rm -f "$ICON_48_FILE" "$ICON_SCALABLE_FILE"
if [[ -f "$LEGACY_DESKTOP_FILE" ]] && grep -Fqx 'Comment=AlienFX lighting studio' "$LEGACY_DESKTOP_FILE"; then
    rm -f "$LEGACY_DESKTOP_FILE"
fi
rm -rf -- "$APP_DIR"
rmdir "$APP_ROOT" 2>/dev/null || true
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DATA_HOME/applications" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1 \
    && [[ -f "$DATA_HOME/icons/hicolor/index.theme" ]]; then
    gtk-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi
printf 'AlienFX Studio was removed. Saved palettes and controller settings were kept.\n'