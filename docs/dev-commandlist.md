# 開発用コマンドリスト

## Migration Flow

```bash
# ソースコード変更をイメージに反映するため再ビルド
docker compose build backend

# Migrationを生成する
docker compose run --rm \
  --user "$(id -u):$(id -g)" \
  --volume ./backend/migrations/versions:/app/migrations/versions \
  backend \
  alembic revision --autogenerate -m "<MIGRATION_MESSAGE>"

# Migrationファイルが生成されたことと内容を確認する
ls -lah backend/migrations/versions/<MIGRATION_FILE_NAME>
cat backend/migrations/versions/<MIGRATION_FILE_NAME>

# Migrationをイメージに反映するため再ビルド
docker compose --env-file ./backend/.env build backend

# 現在のMigration IDを確認する ((head)ではない)
docker compose --env-file ./backend/.env run --rm backend alembic current

# 新しいMigration IDを確認する
docker compose --env-file ./backend/.env run --rm backend alembic heads

# 新しいMigrationをDBに反映させる
docker compose --env-file ./backend/.env run --rm backend alembic upgrade head

# 現在のMigration IDを確認する ((head)=headsのIDになっている)
docker compose --env-file ./backend/.env run --rm backend alembic current

# DBの内容を確認する
docker compose exec db sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "<SQL_QUERY>;"'

# コンテナを再作成する
docker compose --env-file ./backend/.env up -d backend
```

## Deploy / Rollback

`main` へマージすると `.github/workflows/deploy.yml` が自動でデプロイする。
以下はCDが使えないとき、または切り戻すときにVM上で実行する手順。

`TAG` にはGHCRに存在するコミットSHAを指定する（タグはGitHubのコミット履歴、またはPackagesのタグ一覧から取得する）。

```bash
# デプロイ先へ移動し、対象コミットへ揃える（compose.yaml と Caddyfile をイメージと一致させる）
cd <DEPLOY_PATH>
git fetch --prune origin
git switch --detach <commit sha>

# 手動デプロイ（VM上）
make deploy TAG=<commit sha>

# ロールバック（VM上）: 直前に動いていたコミットSHAを指定する
make deploy TAG=<前のcommit sha>

# 適用済みMigrationの確認
docker compose --env-file ./backend/.env run --rm backend alembic current

# 動いているイメージの確認
docker compose --env-file ./backend/.env ps
```

Migrationは前方適用（`upgrade head`）のみ自動化している。イメージを戻してもスキーマは戻らないため、戻す必要がある場合は明示的に実行する。

```bash
docker compose --env-file ./backend/.env run --rm backend alembic downgrade -1
```

`downgrade` は追加したカラムごとデータを失う可能性がある。Migrationは後方互換に保ち、**コードだけロールバックすれば復旧できる**状態を維持する。
