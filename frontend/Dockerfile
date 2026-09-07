# syntax=docker/dockerfile:1

# ----------------------------------------------
# Builder stage
# 依存のインストールとViteのビルドを行う。Nodeはこのステージにしか残らない
# ----------------------------------------------

FROM node:26-bookworm-slim AS builder

WORKDIR /app

# CorepackがpackageManagerフィールドのpnpmを取得する。
# 非対話環境ではダウンロード確認プロンプトが出るため無効化する
ENV PNPM_HOME=/pnpm
ENV PATH="${PNPM_HOME}:${PATH}"
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0

RUN corepack enable pnpm

# 依存だけ先に入れてレイヤーをキャッシュする。ソース変更で再インストールが走らない
COPY package.json pnpm-lock.yaml ./

RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile

COPY . .

# typecheck も通す（package.json の build スクリプト）
RUN pnpm build

# ----------------------------------------------
# Runtime stage
# ビルド成果物だけをCaddyイメージへ載せる
# ----------------------------------------------

FROM caddy:2-alpine AS runtime

COPY --from=builder /app/dist /srv/frontend
