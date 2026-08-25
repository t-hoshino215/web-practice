# Webサーバーの構築と公開の練習用レポジトリ

## Over view

Webサーバーの構築と公開を段階的に練習している。
このサーバーアプリケーションは、FastAPIを使ったシンプルなWeb APIであり、ユーザー認証やメッセージのCRUD操作を提供する。
Webアプリケーション構築のテンプレートとしても利用できるように設計されている。

## Complete learning steps

想定している学習ステップは以下の通り。

1. FastAPIローカル実行: FastAPI・Uvicornを使い、`/`や`/health`へローカルからアクセスする
2. Docker化: Dockerfile作成、イメージのビルド、コンテナ起動
3. Caddy + Compose: CaddyからFastAPIへ転送。FastAPIの8000番は外部非公開
4. OCIへ公開: OCI Ubuntu VM、VCN、Security List、Docker Composeによる公開
5. ドメイン・HTTPS: Cloudflareでドメイン取得、DNS設定、443番開放、Caddyの自動HTTPS
6. PostgreSQL: PostgreSQLコンテナ追加、FastAPIから接続、CRUD、named volumeで永続化
7. DB Migration: Alembic導入、既存DBのstamp、Migration生成、upgrade／downgrade
8. 認証: ユーザーテーブル、登録API、パスワードハッシュ、ログイン、Session／Cookie、保護API
9. フロントエンド-1: HTML/CSS/JavaScriptの静的ファイルを作成し、FastAPIと連携する
10. フロントエンド-2: TypeScript + React + Vite などのフロントエンドフレームワークでフロントエンドを構築し、FastAPIと連携する
11. CI/CD: GitHub Actions、テスト実行、イメージ作成、MigrationとOCIデプロイの自動化
12. 運用基盤: PostgreSQLのBackup／Restore、ログ管理、ヘルスチェック、監視、通知

## Tech Stack

- バックエンド: FastAPI + Uvicorn
  - Python 3.14
  - パッケージマネージャー: uv
  - テスト pytest
  - リンター/フォーマッター: ruff
  - 型チェック: mypy
- フロントエンド: TypeScript + React + Vite
  - パッケージマネージャー: pnpm
  - テスト: vitest
  - リンター/フォーマッター: eslint + prettier
  - 型チェック: TypeScript (tsc)

## Project Structure

- バックエンド: `backend/`
  - ソースコード: `backend/src/web_practice/`
  - テスト: `backend/tests/`（backend/src/web_practice/ のディレクトリ構造をミラー）
  - テストフィクスチャ: `backend/tests/conftest.py` , `backend/tests/factories/`
- フロントエンド: `frontend/`
- ドキュメント: `docs/`
- コーディングルール: `.claude/rules/code-style.md` , `.claude/rules/python-style.md`,  `.claude/rules/typescript-style.md`
- テストルール: `.claude/rules/python-testing.md`, `.claude/rules/typescript-testing.md`

## Core Principles

1. **TDD優先** — 機能追加はテスト作成から始める
2. **検証後に完了報告** — テストがパスするまで完了としない
3. **最小限の変更** — 依頼されていないリファクタリングはしない

## Workflow

- 機能追加・変更を依頼されたら、 `.claude/skills/dev-workflow` のフローに従って実装を行う
- 可能な限りサブエージェントを並列で使用する
- git の変更履歴・詳細の調査は、 `.claude/skills/git-inspect` を使用する
- タスクが完了したら、変更内容のサマリーを表示し、最後に「 === タスク完了 === 」と伝える
