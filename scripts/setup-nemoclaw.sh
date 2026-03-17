#!/bin/bash
# MAGI — NemoClaw Setup for GB10/DGX Spark
# Installs NemoClaw, configures DGX Spark, pulls models, and sets up sandbox
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== MAGI NemoClaw Setup ==="
echo ""

# 1. Check prerequisites
echo "[1/5] Checking prerequisites..."
for cmd in node npm ollama docker; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "  ERROR: $cmd not found. Please install it first."
        exit 1
    fi
done
echo "  ✓ All prerequisites found"

# 2. Install NemoClaw CLI
echo "[2/5] Installing NemoClaw..."
if ! command -v nemoclaw &>/dev/null; then
    if [ -d /tmp/NemoClaw ]; then
        rm -rf /tmp/NemoClaw
    fi
    git clone https://github.com/NVIDIA/NemoClaw.git /tmp/NemoClaw
    cd /tmp/NemoClaw && sudo npm install -g .
    cd "$PROJECT_DIR"
    echo "  ✓ NemoClaw CLI installed"
else
    echo "  ✓ NemoClaw already installed: $(nemoclaw --version 2>/dev/null || echo 'version unknown')"
fi

# 3. DGX Spark specific setup (cgroup v2 + Docker config)
echo "[3/5] Running DGX Spark setup..."
if [ "$(uname -m)" = "aarch64" ]; then
    nemoclaw setup-spark
    echo "  ✓ Spark-specific setup complete"
else
    echo "  ⚠ Not aarch64, skipping Spark-specific setup"
fi

# 4. Pull Ollama models (3 different models for 3 agents)
echo "[4/5] Pulling models..."
echo "  MELCHIOR: qwen3.5:9b (6.6GB)..."
ollama pull qwen3.5:9b || echo "  ⚠ Pull failed (may already exist)"
echo "  BALTHASAR: nemotron-9b-n6-nothink (6.5GB)..."
ollama pull nemotron-9b-n6-nothink || echo "  ⚠ Pull failed (may already exist)"
echo "  CASPER: gemma3:12b (8.1GB)..."
ollama pull gemma3:12b || echo "  ⚠ Pull failed (may already exist)"

# 5. Set up NemoClaw sandbox with MAGI workspace
echo "[5/5] Setting up NemoClaw sandbox..."
if command -v openclaw &>/dev/null && openclaw nemoclaw migrate --dry-run 2>/dev/null; then
    echo "  Migrating existing OpenClaw workspace..."
    openclaw nemoclaw migrate
    echo "  ✓ Migration complete"
else
    echo "  Running fresh NemoClaw setup..."
    nemoclaw setup
    echo ""
    echo "  To manually copy MAGI workspace into sandbox:"
    echo "    nemoclaw <sandbox-name> connect"
    echo "    # Then copy openclaw-workspace/ contents"
fi

echo ""
echo "=== NemoClaw Setup Complete ==="
echo ""
echo "To start MAGI:"
echo "  1. Dashboard:  cd scripts && uvicorn server:app --host 0.0.0.0 --port 8000"
echo "  2. NemoClaw:   nemoclaw term"
echo "  3. Chat:       nemoclaw <sandbox-name> connect && openclaw chat"
echo ""
echo "Dashboard: http://localhost:8000"
echo "OpenClaw:  http://localhost:18789 (inside NemoClaw sandbox)"
