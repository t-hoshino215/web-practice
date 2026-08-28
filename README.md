# Web Practice

Webサーバーの構築と公開を段階的に練習するためのレポジトリ。

FastAPIによるWeb API（ユーザー認証・メッセージのCRUD）を題材に、ローカル実行 → Docker化 → リバースプロキシ → クラウド公開 → HTTPS → DB → Migration → 認証、と一段ずつ積み上げている。
Webアプリケーション構築のテンプレートとしても利用できるように設計している。

- 公開API: `https://api.taph-lab.com`
- APIドキュメント（Swagger UI）: `https://api.taph-lab.com/docs`

## Tech Stack

| 領域 | 採用技術 |
| --- | --- |
| 言語 | Python 3.14 |
| Webフレームワーク | FastAPI / Uvicorn |
| ORM | SQLAlchemy 2.x |
| Migration | Alembic |
| DB | PostgreSQL 18 |
| パスワードハッシュ | pwdlib（Argon2） |
| フロントエンド | TypeScript / React / Vite / Zod |
| リバースプロキシ | Caddy 2（自動HTTPS） |
| 実行環境 | Docker / Docker Compose |
| ホスティング | Oracle Cloud Infrastructure（Ubuntu VM） |
| DNS・ドメイン | Cloudflare |
| パッケージ管理 | uv / pnpm |
| テスト | pytest / pytest-cov / Vitest |
| Lint・Format | ruff / ESLint / Prettier |
| 型チェック | mypy / TypeScript (tsc) |

## Architecture

### Runtime

```text
Internet
  ↓ HTTPS (443)
Caddy               … 自動HTTPS・リクエストの振り分け
  ├─ /*             → React（Viteのビルド成果物を静的配信）
  └─ /api/*         → FastAPI (backend:8000、外部非公開)
                         ↓ psycopg
PostgreSQL (db)     … named volume で永続化
```

### Repository layout

```text
.
├── backend/                     # FastAPIアプリケーション
│   ├── src/web_practice/        # アプリ本体（src レイアウト）
│   │   ├── main.py              # FastAPIの組み立て・ライフサイクル
│   │   ├── config.py            # 環境変数・Cookie設定
│   │   ├── database.py          # Engine・Session・Base
│   │   ├── models/              # SQLAlchemy DBモデル
│   │   │   ├── message.py
│   │   │   ├── user.py
│   │   │   └── auth_session.py
│   │   ├── schemas/             # API入出力のPydanticモデル
│   │   │   ├── message.py
│   │   │   ├── user.py
│   │   │   └── auth.py
│   │   ├── dependencies/        # FastAPI Dependency
│   │   │   ├── auth.py          # Session検証・ユーザー取得・admin判定
│   │   │   └── csrf.py          # CSRFトークン検証
│   │   ├── routers/             # HTTPエンドポイント
│   │   │   ├── health.py
│   │   │   ├── messages.py
│   │   │   ├── users.py
│   │   │   ├── admin.py
│   │   │   └── auth.py
│   │   └── services/            # 認証などのアプリ内部処理
│   │       └── auth.py
│   ├── tests/                   # pytest（src配下の構造をミラー）
│   ├── migrations/              # Alembic Migration
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile               # 本番用イメージ（builder / runtime）
├── frontend/                    # TypeScript + React + Vite
│   ├── src/
│   │   ├── api/                 # APIクライアント・Zodスキーマ
│   │   ├── components/          # UIコンポーネント
│   │   ├── hooks/               # 認証・メッセージの状態管理
│   │   ├── styles/              # グローバルCSS
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── tests/                   # Vitest共通セットアップ・factory
│   ├── index.html               # Viteのエントリポイント
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── eslint.config.js
│   └── Dockerfile               # Vite build + Caddyの多段ビルド
├── docs/
│   ├── guides/                  # 段階的な導入手順書
│   ├── dev-commandlist.md       # 開発用コマンド集
│   ├── healthcheck.md           # 疎通確認コマンド集
│   ├── plans/                   # 実装計画
│   └── logs/                    # 作業ログ
├── scripts/gen-compose-env.sh   # ホスト環境から .env を生成
├── .devcontainer/               # VS Code Dev Container 設定
├── compose.yaml                 # dev / backend / db / caddy
├── Caddyfile                    # リバースプロキシ設定
├── Dockerfile                   # 開発コンテナ用イメージ
└── Makefile                     # セットアップ・起動のショートカット
```

### Data Flow

```text
routers/     … HTTPの入口。認証・CSRFのDependencyを適用する
  ↓
services/    … パスワードハッシュ・トークン生成などのアプリ内部処理
  ↓
schemas/     … API入出力の検証（Pydantic）
  ↓
models/      … DBスキーマの定義（SQLAlchemy）
  ↓
database.py  … Engine・Session・Base
```

## API

認証はHttpOnly Session Cookieで行う。ログイン時には、JavaScriptから読み取れる `csrf_token` Cookieも発行する。
状態変更エンドポイントは、`X-CSRF-Token` ヘッダー、CSRF Cookie、認証セッションに保存したCSRFトークンのハッシュの3者を照合する Double Submit Cookie 方式で保護する。フロントエンドは状態変更の直前にCookieを読み、ヘッダーへ設定する。

認証済みセッションでCSRF Cookieだけが欠落した場合は `POST /api/auth/csrf` で再発行できる。ログインレスポンスの `csrf_token` は互換性のため維持しているが、ReactフロントエンドではCookieを正本として扱う。

| Method | Path | 認証 | CSRF | 説明 |
| --- | --- | --- | --- | --- |
| GET | `/` | - | - | 動作確認用のメッセージ |
| GET | `/health` | - | - | アプリのヘルスチェック |
| GET | `/db-health` | - | - | DB接続のヘルスチェック |
| POST | `/users` | - | - | ユーザー登録（重複は409） |
| POST | `/login` | - | - | ログイン。Session Cookie・CSRF Cookie発行＋CSRFトークン返却 |
| POST | `/auth/csrf` | 必要 | - | 現在のセッションに紐づくCSRFトークンとCookieを再発行 |
| POST | `/logout` | 必要 | 必要 | ログアウト。Session削除＋両Cookie削除 |
| GET | `/users/me` | 必要 | - | ログイン中のユーザー情報 |
| GET | `/messages` | 必要 | - | 自分のメッセージ一覧 |
| POST | `/messages` | 必要 | 必要 | メッセージ作成 |
| PATCH | `/messages/{message_id}/archive` | 必要 | 必要 | メッセージのアーカイブ |
| GET | `/admin/users` | admin | - | 全ユーザー一覧 |
| GET | `/admin/messages` | admin | - | 全メッセージ一覧 |

疎通確認の具体的なコマンドは [docs/healthcheck.md](docs/healthcheck.md) を参照。

## Getting Started

### 1. 環境変数を用意する

ホスト環境に合わせて開発コンテナ用の `.env` を生成する。

```bash
bash scripts/gen-compose-env.sh
```

アプリ用の環境変数は `backend/.env` に用意する。

```bash
POSTGRES_DB=<データベース名>
POSTGRES_USER=<ユーザー名>
POSTGRES_PASSWORD=<パスワード>
COOKIE_SECURE=false   # 公開HTTPS環境では true
```

`.env` および `backend/.env` は `.gitignore` 済み。認証情報をコミットしないこと。

### 2. アプリケーションを起動する

```bash
# backend / db / caddy を起動する
make up

# ヘルスチェック
curl -i http://localhost/health
curl -i http://localhost/db-health
```

### 3. 開発コンテナを使う場合

```bash
# Docker network と volume を作成し、dev コンテナを起動する
make up-dev

# dev コンテナに入る
make exec-dev
```

VS Codeの場合は Dev Container として `.devcontainer/devcontainer.json` から起動できる。

### 4. テスト・Lint・型チェック

`backend/` ディレクトリで実行する。

```bash
uv sync                 # 依存関係の同期
uv run pytest           # テスト
uv run pytest --cov     # カバレッジ付きテスト
uv run ruff check .     # Lint
uv run ruff format .    # Format
uv run mypy src         # 型チェック
```

### 5. フロントエンド開発

フロントエンドの開発コマンドは `frontend/` ディレクトリで実行する。

```bash
pnpm install          # 依存関係の同期
pnpm dev              # Vite開発サーバー
pnpm test             # テスト
pnpm test:coverage    # カバレッジ付きテスト
pnpm typecheck        # 型チェック
pnpm lint             # Lint
pnpm format:check     # Formatチェック
pnpm build            # 本番用ビルド
```

### 6. Migration

生成・適用の詳細な手順は [docs/dev-commandlist.md](docs/dev-commandlist.md) を参照。

```bash
docker compose run --rm backend alembic current   # 現在のリビジョン
docker compose run --rm backend alembic upgrade head
```

## STEP

### 完了

| STEP | 目的 | 主な内容 |
| --- | --- | --- |
| 1. FastAPIローカル実行 | Web APIの基本を理解する | FastAPI・Uvicornを使い、`/` や `/health` へローカルからアクセス |
| 2. Docker化 | 実行環境をコンテナとして再現可能にする | Dockerfile作成、イメージのビルド、コンテナ起動 |
| 3. Caddy + Compose | 複数コンテナとリバースプロキシを学ぶ | CaddyからFastAPIへ転送。FastAPIの8000番は外部非公開 |
| 4. OCIへ公開 | クラウド上でWebサーバーを公開する | OCI Ubuntu VM、VCN、Security List、Docker Composeによる公開 |
| 5. ドメイン・HTTPS | IPアドレスではなく安全なURLで公開する | Cloudflareでドメイン取得、DNS設定、443番開放、Caddyの自動HTTPS |
| 6. PostgreSQL | アプリで永続データを扱う | PostgreSQLコンテナ追加、FastAPIから接続、CRUD、named volumeで永続化 |
| 7. DB Migration | DBスキーマの変更履歴を管理する | Alembic導入、既存DBのstamp、Migration生成、upgrade／downgrade |
| 8. 認証 | ユーザーごとにアクセスを制御する | ユーザーテーブル、登録API、パスワードハッシュ、ログイン、Session／Cookie、CSRF、保護API |
| [9. フロントエンド-1](docs/guides/step09-static-frontend.md) | ブラウザから使えるUIを用意する | HTML/CSS/JavaScriptの静的ファイルを作成し、Caddyから配信してAPIと連携する |
| [10. フロントエンド-2](docs/guides/step10-react-vite.md) | モダンなフロントエンド開発を学ぶ | TypeScript + React + Vite でフロントエンドを再構築し、ビルド成果物を配信する |

### 予定

| STEP | 目的 | 主な内容 | 手順書 |
| --- | --- | --- | --- |
| 11. CI/CD | テストとデプロイを自動化する | GitHub Actions、テスト実行、イメージ作成、MigrationとOCIデプロイの自動化 | - |
| 12. 運用基盤 | 障害やデータ消失に備えて継続運用する | PostgreSQLのBackup／Restore、ログ管理、ヘルスチェック、監視、通知 | - |

## Documentation

| ドキュメント | 内容 |
| --- | --- |
| [docs/guides/](docs/guides/) | 各STEPの段階的な導入手順書 |
| [docs/healthcheck.md](docs/healthcheck.md) | ローカル／公開サーバーの疎通確認コマンド集 |
| [docs/dev-commandlist.md](docs/dev-commandlist.md) | Migrationなど開発時のコマンド集 |
| [docs/plans/](docs/plans/) | 実装前に作成した計画書 |
| [docs/logs/](docs/logs/) | 実装後に記録した作業ログ |
| [CLAUDE.md](CLAUDE.md) | AIエージェント向けのプロジェクト規約 |
