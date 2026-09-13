#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# ApniPehChaan — One-Command Demo Launcher
# ═══════════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PORT=8000

echo "═══════════════════════════════════════════════════════════════"
echo "  ApniPehChaan — Setup & Launch"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Step 1: Create virtual environment if needed
if [ ! -d "$VENV_DIR" ]; then
    echo "[1/4] Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip -q
else
    echo "[1/4] Virtual environment exists ✓"
fi

# Step 2: Install dependencies
echo "[2/4] Installing dependencies..."
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q

# Step 3: Build datasets
echo "[3/4] Building datasets..."
if [ ! -f "$SCRIPT_DIR/data/breaches/hibp_breaches.json" ]; then
    "$VENV_DIR/bin/python" "$SCRIPT_DIR/data/download_datasets.py"
else
    echo "    Datasets already present — skipping download."
fi

# Step 4: Launch server
echo ""
echo "[4/4] Launching ApniPehChaan server on port $PORT..."
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Dashboard: http://127.0.0.1:$PORT"
echo "  API Docs:  http://127.0.0.1:$PORT/docs"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# No --reload. It watches the project directory, and a file touched mid-demo
# restarts the process. State now lives in sqlite so a restart is survivable,
# but a reload still drops live WebSocket connections mid-agent-run.
# Use scripts/dev.sh if you want auto-reload while developing.
"$VENV_DIR/bin/python" -m uvicorn backend.app:app --host 0.0.0.0 --port $PORT
