#!/usr/bin/env bash
set -eu

cat > .env.dev <<ENV
USER_NAME=$(id -un)
USER_UID=$(id -u)
USER_GID=$(id -g)
PROJECT_DIR=$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")
CONTAINER_WORKSPACE=/workspace
SHARED_DATA_DIR=$HOME/dev/shared-data/
CONTAINER_SHARED_DATA=/data/shared
TZ=$(timedatectl show -p Timezone --value 2>/dev/null || echo UTC)
NODE_VERSION=24
PYTHON_VERSION=3.14
UV_VERSION=0.12.5
HOST_BACKEND_PORT=${HOST_BACKEND_PORT:-8000}
ENV
