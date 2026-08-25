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
