# [Project Name]

## Over view

[アプリケーションなどの説明]

## Tech Stack

- Python 3.13
- パッケージマネージャー: uv
- テスト pytest
- リンター/フォーマッター: ruff
- 型チェック: mypy

## Project Structure

- ソースコード: `src/`
- テスト: `tests/`（src/ のディレクトリ構造をミラー）
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
