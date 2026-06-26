#!/bin/bash
# Install polymarket-mcp server for mcporter
# Usage: bash scripts/install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && cd .. && pwd)"
MCP_FILE="${SCRIPT_DIR}/polymarket_mcp.py"

if [ ! -f "$MCP_FILE" ]; then
    echo "Error: $MCP_FILE not found. Run from the polymarket-mcp directory." >&2
    exit 1
fi

# Check mcporter
if ! command -v mcporter &> /dev/null; then
    echo "mcporter not found. Installing..."
    npm install -g mcporter 2>/dev/null || npm install -g mcporter --prefix /workspace/.npm-global 2>/dev/null || {
        echo "Could not install mcporter. Install manually: npm install -g mcporter"
        exit 1
    }
fi

PYTHON=$(which python3)
if [ -z "$PYTHON" ]; then
    PYTHON=$(which python)
fi

echo "Installing polymarket-mcp server..."
mcporter config add polymarket --command "$PYTHON" --arg "$MCP_FILE"

echo "Done! Try: mcporter call polymarket.market_summary"
