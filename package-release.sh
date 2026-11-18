#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
OUTPUT="${1:-$PROJECT_DIR/../alienfx-studio-linux.tar.gz}"
OUTPUT="$(realpath -m -- "$OUTPUT")"

case "$OUTPUT" in
    "$PROJECT_DIR"/*)
        printf 'Choose an archive path outside the project directory.\n' >&2
        exit 1
        ;;
esac

mkdir -p "$(dirname -- "$OUTPUT")"
tar -C "$PROJECT_DIR" \
    --exclude=.git \
    --exclude=.venv \
    --exclude=__pycache__ \
    --exclude='*.py[cod]' \
    --exclude=.pytest_cache \
    --exclude=build \
    --exclude=dist \
    --exclude='*.egg-info' \
    -czf "$OUTPUT" .
printf 'Created %s\n' "$OUTPUT"