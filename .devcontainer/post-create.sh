#!/usr/bin/env bash
# Runs once after container creation.
set -euo pipefail
echo "Installing dependencies..."
cd __CONTAINER_WORKSPACE__ && uv sync
echo "Done."
