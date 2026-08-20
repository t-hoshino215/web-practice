#!/usr/bin/env bash
# Runs once after container creation.
set -euo pipefail
echo "Installing dependencies..."
cd /workspace/app && uv sync
cd /workspace
echo "Done."
