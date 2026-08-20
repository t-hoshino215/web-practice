# syntax=docker/dockerfile:1

ARG PYTHON_VERSION
ARG UV_VERSION

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# =============================================================================
# base: shared OS setup + non-root user (foundation for every purpose stage)
# =============================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS base

COPY --from=uv /uv /uvx /usr/local/bin/

# Build arguments: provided via .env + Compose (see scripts/gen-compose-env.sh)
ARG USER_NAME
ARG USER_UID
ARG USER_GID
ARG CONTAINER_WORKSPACE
ARG TZ

# Write build args to environment variables for use in later stages and at runtime.
ENV USER_NAME=${USER_NAME}
ENV USER_UID=${USER_UID}
ENV USER_GID=${USER_GID}
ENV CONTAINER_WORKSPACE=${CONTAINER_WORKSPACE}
ENV TZ=${TZ}
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:${PATH}"

# Python and uv environment variables
ENV UV_LINK_MODE=copy
ENV UV_CACHE_DIR=/home/${USER_NAME}/.cache/uv
# Keep the project venv outside the bind-mounted workspace.
# A volume mounted inside the bind mount makes dockerd create a root-owned
# app/.venv on the host; an out-of-tree path avoids touching the host at all.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Non-root user setup
RUN userdel -r pwuser 2>/dev/null || true \
    && groupadd --gid "${USER_GID}" "${USER_NAME}" 2>/dev/null || true \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" --create-home --shell /bin/bash "${USER_NAME}" \
    && mkdir -p "${CONTAINER_WORKSPACE}" /opt/venv \
    && chown -R "${USER_UID}:${USER_GID}" "${CONTAINER_WORKSPACE}" /opt/venv \
    && ln -sf /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo "${TZ}" > /etc/timezone

WORKDIR ${CONTAINER_WORKSPACE}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        tzdata \
    && rm -rf /var/lib/apt/lists/*


# =============================================================================
# dev: development environment
# =============================================================================
FROM base AS dev

ARG NODE_VERSION

USER root

# Install OS tools for development
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        procps \
        iputils-ping \
        netcat-openbsd \
        zsh \
        openssh-client \
        build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g markdownlint-cli2

# Switch the login shell to zsh and create the dev config + uv cache dirs
RUN chsh -s /bin/zsh "${USER_NAME}" \
    && mkdir -p \
        "/home/${USER_NAME}/.config" \
        "/home/${USER_NAME}/.claude" \
    && chown -R "${USER_UID}:${USER_GID}" \
        "/home/${USER_NAME}/.config" \
        "/home/${USER_NAME}/.claude"

COPY . "${CONTAINER_WORKSPACE}"/

# Switch to non-root user
USER ${USER_NAME}

RUN curl -fsSL https://claude.ai/install.sh | bash \
    && curl -fsSL https://chatgpt.com/codex/install.sh | sh

EXPOSE 8000

CMD ["sleep", "infinity"]
