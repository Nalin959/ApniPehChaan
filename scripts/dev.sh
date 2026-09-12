#!/usr/bin/env bash
# Development launcher with auto-reload. Do not use this for the demo:
# a reload drops live WebSocket connections mid agent run.
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python -m uvicorn backend.app:app --host 0.0.0.0 --port "${PORT:-8000}" \
    --reload --reload-dir backend --reload-dir frontend
