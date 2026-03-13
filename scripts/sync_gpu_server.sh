#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${LAB_GPU_HOST:-}" ]]; then
  echo "LAB_GPU_HOST is required, for example user@gpu-host" >&2
  exit 1
fi

if [[ -z "${LAB_GPU_PATH:-}" ]]; then
  echo "LAB_GPU_PATH is required, for example /srv/lab-manager" >&2
  exit 1
fi

rsync \
  --archive \
  --verbose \
  --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude 'ocr-benchmark/data/renders/' \
  --exclude 'ocr-benchmark/results/' \
  "$ROOT_DIR/" \
  "$LAB_GPU_HOST:$LAB_GPU_PATH/"

echo "Synced to $LAB_GPU_HOST:$LAB_GPU_PATH"
