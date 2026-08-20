# Webサーバーの構築と公開の練習用レポジトリ

## Over view

Webサーバーの構築と公開を段階的に練習している。

## Learning steps

1. FastAPIローカル実行: FastAPI・Uvicornを使い、`/`や`/health`へローカルからアクセスする
2. Docker化: Dockerfile作成、イメージのビルド、コンテナ起動
3. Caddy + Compose: CaddyからFastAPIへ転送。FastAPIの8000番は外部非公開
4. GitHub Actions: CI/CDの自動化。テスト・Lint・Build・Deployを自動化する
5. OCIへ公開: OCI Ubuntu VM、VCN、Security List、Docker Composeによる公開
6. ドメイン・HTTPS: Cloudflareでドメイン取得、DNS設定、443番開放、Caddyの自動HTTPS
7. PostgreSQL: PostgreSQLコンテナ追加、FastAPIから接続、CRUD、named volumeで永続化
8. DB Migration: Alembic導入、既存DBのstamp、Migration生成、upgrade／downgrade
9. 認証: ユーザーテーブル、登録API、パスワードハッシュ、ログイン、Session／Cookie、保護API

## Tech Stack

- Python 3.14
- パッケージマネージャー: uv
- テスト pytest
- リンター/フォーマッター: ruff
- 型チェック: mypy

## Project Structure

- ソースコード: `app/`
- テスト: `tests/`（app/ のディレクトリ構造をミラー）
- テストフィクスチャ: `tests/conftest.py` , `tests/factories/`
- ドキュメント: `docs/`
- コーディングルール: `.claude/rules/code-style.md` , `.claude/rules/python-style.md`
- テストルール: `.claude/rules/python-testing.md`

## Core Principles

1. **TDD優先** — 機能追加はテスト作成から始める
2. **検証後に完了報告** — テストがパスするまで完了としない
3. **最小限の変更** — 依頼されていないリファクタリングはしない

## Workflow

- 機能追加・変更を依頼されたら、 `.claude/skills/dev-workflow` のフローに従って実装を行う
- 可能な限りサブエージェントを並列で使用する
- git の変更履歴・詳細の調査は、 `.claude/skills/git-inspect` を使用する
- タスクが完了したら、変更内容のサマリーを表示し、最後に「 === タスク完了 === 」と伝える
