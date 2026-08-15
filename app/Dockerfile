# syntax=docker/dockerfile:1

# ----------------------------------------------
# Dependency builder stage
# 依存ファイルを先にビルドしてキャッシュすることで、ソースコードの変更があっても依存関係の再インストールを避ける
# ----------------------------------------------

FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.5 \
    /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
    --locked \
    --no-dev \
    --no-install-project

# ----------------------------------------------
# Runtime stage
# ----------------------------------------------

FROM python:3.14-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

RUN useradd \
    --create-home \
    --uid 10001 \
    appuser

COPY --from=builder /app/.venv /app/.venv

COPY --chown=appuser:appuser \
    main.py \
    alembic.ini \
    ./

COPY --chown=appuser:appuser \
    alembic \
    ./alembic

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]