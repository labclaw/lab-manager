#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but not installed" >&2
  exit 1
fi

uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e .

echo "Environment ready at $ROOT_DIR/.venv"
