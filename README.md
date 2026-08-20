# Web Practice

Webサーバーの構築と公開の練習用レポジトリ

## Architecture

ソースコードの構造

```text
app/
├── main.py
├── database.py
├── config.py
├── models/
│   ├── __init__.py
│   ├── message.py
│   ├── user.py
│   └── auth_session.py
├── schemas/
│   ├── __init__.py
│   ├── message.py
│   ├── user.py
│   └── auth.py
├── dependencies/
│   ├── __init__.py
│   ├── auth.py
│   └── csrf.py
├── routers/
│   ├── __init__.py
│   ├── health.py
│   ├── messages.py
│   ├── users.py
│   └── auth.py
├── services/
│   ├── __init__.py
│   └── auth.py
├── alembic.ini
├── alembic/
├── pyproject.toml
└── Dockerfile
```

## Data Flow

```text
main.py
  ↓ FastAPIアプリを組み立てるだけ

routers/
  ↓ HTTP API

services/
  ↓ 認証などのアプリ内部処理

schemas/
  ↓ API入出力のPydanticモデル

models/
  ↓ SQLAlchemy DBモデル

database.py
  ↓ DB接続・Session・Base
```


## STEP

| STEP               | 状態 | 目的                    | 主な内容                                                |
| ------------------ | -- | --------------------- | --------------------------------------------------- |
| 1. FastAPIローカル実行   | 完了 | Web APIの基本を理解する       | FastAPI・Uvicornを使い、`/`や`/health`へローカルからアクセス         |
| 2. Docker化         | 完了 | 実行環境をコンテナとして再現可能にする   | Dockerfile作成、イメージのビルド、コンテナ起動                        |
| 3. Caddy + Compose | 完了 | 複数コンテナとリバースプロキシを学ぶ    | CaddyからFastAPIへ転送。FastAPIの8000番は外部非公開               |
| 4. OCIへ公開          | 完了 | クラウド上でWebサーバーを公開する    | OCI Ubuntu VM、VCN、Security List、Docker Composeによる公開 |
| 5. ドメイン・HTTPS      | 完了 | IPアドレスではなく安全なURLで公開する | Cloudflareでドメイン取得、DNS設定、443番開放、Caddyの自動HTTPS        |
| 6. PostgreSQL      | 完了 | アプリで永続データを扱う          | PostgreSQLコンテナ追加、FastAPIから接続、CRUD、named volumeで永続化  |
| 7. DB Migration    | 完了 | DBスキーマの変更履歴を管理する      | Alembic導入、既存DBのstamp、Migration生成、upgrade／downgrade  |
| 8. 認証              | 完了 | ユーザーごとにアクセスを制御する      | ユーザーテーブル、登録API、パスワードハッシュ、ログイン、Session／Cookie、保護API  |
| 9. CI/CD           | 予定 | テストとデプロイを自動化する        | GitHub Actions、テスト実行、イメージ作成、MigrationとOCIデプロイの自動化   |
| 10. 運用基盤           | 予定 | 障害やデータ消失に備えて継続運用する    | PostgreSQLのBackup／Restore、ログ管理、ヘルスチェック、監視、通知        |
