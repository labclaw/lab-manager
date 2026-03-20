#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose --env-file .env.example config -q
uv run pytest tests/test_release_gate.py -q
uv run pytest tests/bdd/step_defs/test_api_security.py -q
