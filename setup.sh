#!/bin/bash
# MAGI — GB10/DGX Spark Setup Script
set -euo pipefail

echo "=== MAGI System Setup ==="
echo ""

# 1. Check Ollama
echo "[1/5] Checking Ollama..."
if ! command -v ollama &>/dev/null; then
    echo "ERROR: Ollama not found. Install from https://ollama.com"
    exit 1
fi
echo "  ✓ Ollama found"

# 2. Pull required models (3 different models for 3 agents)
echo "[2/5] Pulling models..."
echo "  MELCHIOR: qwen3.5:9b (6.6GB)..."
ollama pull qwen3.5:9b || echo "  ⚠ Pull failed (may already exist)"
echo "  BALTHASAR: nemotron-9b-n6-nothink (6.5GB)..."
ollama pull nemotron-9b-n6-nothink || echo "  ⚠ Pull failed (may already exist)"
echo "  CASPER: gemma3:12b (8.1GB)..."
ollama pull gemma3:12b || echo "  ⚠ Pull failed (may already exist)"

# 3. Set Ollama environment
echo "[3/5] Setting Ollama configuration..."
export OLLAMA_KEEP_ALIVE=120m
export OLLAMA_MAX_LOADED_MODELS=3
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_HOST=0.0.0.0:11434
echo "  ✓ KEEP_ALIVE=120m, MAX_LOADED_MODELS=2"

# 4. Initialize directories
echo "[4/5] Initializing directories..."
mkdir -p data/cache/eco data/cache/human data/cache/culture data/provided
mkdir -p memory/debates memory/verdicts memory/anomalies
chmod +x scripts/*.py scripts/*.sh 2>/dev/null || true
echo "  ✓ Directories ready"

# 5. Check OpenClaw
echo "[5/5] Checking OpenClaw..."
if command -v openclaw &>/dev/null; then
    echo "  ✓ OpenClaw found: $(openclaw --version 2>/dev/null || echo 'version unknown')"
else
    echo "  ⚠ OpenClaw not found. Install with: curl -fsSL https://openclaw.ai/install.sh | bash"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start MAGI Dashboard:"
echo "  cd scripts"
echo "  python3 -m venv ../.venv && source ../.venv/bin/activate"
echo "  pip install -r requirements.txt"
echo "  MAGI_CONFIG=../config.json uvicorn server:app --host 0.0.0.0 --port 8000"
echo "  → Open http://localhost:8000"
echo ""
echo "To switch domain:"
echo "  ./scripts/switch_domain.sh eco|human|culture"
echo ""
echo "=== NemoClaw (Recommended) ==="
echo "For NemoClaw sandbox setup (OpenShell + policy control):"
echo "  ./scripts/setup-nemoclaw.sh"
echo ""
echo "Memory budget:"
ollama list 2>/dev/null | head -5 || echo "  (run 'ollama list' to check loaded models)"
