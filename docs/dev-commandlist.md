# 開発用コマンドリスト

## Migration Flow

```bash
# ソースコード変更をイメージに反映するため再ビルド
docker compose build app

# Migrationを生成する
docker compose run --rm \
  --user "$(id -u):$(id -g)" \
  --volume ./app/alembic/versions:/app/alembic/versions \
  app \
  alembic revision --autogenerate -m "<MIGRATION_MESSAGE>"

# Migrationファイルが生成されたことと内容を確認する
ls -lah app/alembic/versions/<MIGRATION_FILE_NAME>
cat app/alembic/versions/<MIGRATION_FILE_NAME>

# Migrationをイメージに反映するため再ビルド
docker compose build app

# 現在のMigration IDを確認する ((head)ではない)
docker compose run --rm app alembic current

# 新しいMigration IDを確認する
docker compose run --rm app alembic heads

# 新しいMigrationをDBに反映させる
docker compose run --rm app alembic upgrade head

# 現在のMigration IDを確認する ((head)=headsのIDになっている)
docker compose run --rm app alembic current

# DBの内容を確認する
docker compose exec db sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "<SQL_QUERY>;"'

# コンテナを再作成する
docker compose up -d app
```
