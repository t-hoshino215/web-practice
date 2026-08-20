# 実装計画: テストスイートの `app/` 配下への移行

## 概要

プロジェクト直下の `tests/` を `app/tests/` へ移動し、`app/` を起点にテスト・Lint・型チェックを実行できる構成へ変更する。テストの振る舞いは変えず、ファイル位置に依存するパス解決、pytest・coverage・Docker の設定、プロジェクト内の現行ルール記載のみを整合させる。

## 要件

- 既存の `tests/` 全28ファイルを、ディレクトリ構造を維持したまま `app/tests/` へ移動する。
- pytest の探索先と Python import path を、移動後の構成に合わせる。
- テスト内の `Path(__file__)` 基準のアプリケーションパスを、移動後も同じ対象を指すよう修正する。
- `tests.factories` など既存のテストパッケージ import は維持する。
- coverage の計測対象と本番 Docker image の内容を移動前と同等に保ち、テストコードを除外する。
- 現行のプロジェクト構成・テストルールに記載されたパスを更新する。
- 過去時点の記録である既存の `docs/plans/` と `docs/logs/` は変更しない。

## 影響範囲

| ファイルパス | 変更種別 | 変更内容の概要 |
| --- | --- | --- |
| `tests/**` → `app/tests/**` | 移動 | 全28テストファイルを既存構造のまま移動 |
| `app/tests/conftest.py` | 修正 | `APP_DIR` を移動後の階層に合わせる |
| `app/tests/test_config.py` | 修正 | `config.py` の解決パスを移動後の階層に合わせる |
| `app/tests/test_database.py` | 修正 | `APP_DIR` と subprocess 内の import 経路を移動後の構成に合わせる |
| `app/tests/alembic/test_migrations.py` | 修正 | `alembic.ini` の基準ディレクトリを移動後の階層に合わせる |
| `app/pyproject.toml` | 修正 | pytest の `pythonpath`・`testpaths` と coverage の除外設定を更新 |
| `app/.dockerignore` | 修正 | 本番 image の build context から `tests/` を除外 |
| `CLAUDE.md`（`AGENTS.md` のリンク先） | 修正 | Project Structure のテスト・fixture パスを更新 |
| `.claude/rules/python-testing.md` | 修正 | テスト配置例と factory パスを更新 |

## 実装ステップ

### フェーズ1: テストスイートの移動とパス修正

1. **テストディレクトリの移動** - (ファイル: `tests/**`, `app/tests/**`)
   - アクション: 全28ファイルをディレクトリ構造を維持して `app/tests/` へ移動する。
   - 理由: テストスクリプトをアプリケーションプロジェクトと同じルートに集約するため。
   - 依存関係: なし。
   - リスク: 低。Git の rename として追跡できるよう内容変更を最小化する。

2. **ファイル位置依存パスの修正** - (ファイル: `app/tests/conftest.py`, `app/tests/test_config.py`, `app/tests/test_database.py`, `app/tests/alembic/test_migrations.py`)
   - アクション: `Path(__file__)` から `app/` を求める親階層を更新し、subprocess が `app/tests` を import するよう整える。
   - 理由: 移動前の `/ "app"` 連結を残すと `app/app` を参照してテストが失敗するため。
   - 依存関係: ステップ1。
   - リスク: 中。通常 pytest だけでなく subprocess と Alembic の作業ディレクトリにも影響する。

### フェーズ2: 設定と現行ドキュメントの整合

3. **pytest・coverage 設定の更新** - (ファイル: `app/pyproject.toml`)
   - アクション: `pythonpath` を `["."]`、`testpaths` を `["tests"]` とし、coverage の `omit` に `tests/*` を追加する。
   - 理由: `cd app` を基準に探索・import を完結させ、移動前と同様にテストコード自体を coverage 対象外に保つため。
   - 依存関係: ステップ1。
   - リスク: 低。

4. **本番 Docker build context の維持** - (ファイル: `app/.dockerignore`)
   - アクション: `tests/` を除外対象へ追加する。
   - 理由: 移動前は本番 build context 外だったテストコードが、移動後の runtime image に混入するのを防ぐため。
   - 依存関係: ステップ1。
   - リスク: 低。Docker build 内ではテストを実行していないため、build 手順への影響はない。

5. **現行ルールのパス更新** - (ファイル: `CLAUDE.md`, `.claude/rules/python-testing.md`)
   - アクション: `tests/`、`tests/conftest.py`、`tests/factories/` の記載を `app/tests/` 基準へ変更する。
   - 理由: 今後の開発で旧配置にテストが追加されるのを防ぐため。
   - 依存関係: ステップ1。
   - リスク: 低。

### フェーズ3: 検証

6. **テストと静的検査の実行** - (対象: `app/`, `app/tests/`)
   - アクション: `cd app` で pytest、branch coverage、Ruff check、Ruff format check、mypy を実行する。さらにリポジトリ直下に旧 `tests/` が残っていないことと、Docker image build が成功することを確認する。
   - 理由: 移動後の探索、import、パス解決、品質検査、本番 build context がすべて正常であることを確認するため。
   - 依存関係: ステップ1〜5。
   - リスク: 中。PostgreSQL 専用 URL 未設定時の Migration integration test は、既存仕様どおり skip を許容する。

## テスト戦略

- ユニットテスト: `cd app && uv run pytest -c pyproject.toml -m unit`
- 統合テスト: `cd app && uv run pytest -c pyproject.toml -m integration`（専用 PostgreSQL 未設定の1件は既存仕様どおり skip 可）
- 全体テスト: `cd app && uv run pytest -c pyproject.toml`
- Coverage: `cd app && uv run pytest -c pyproject.toml --cov=. --cov-branch --cov-report=term-missing`
- Lint/Format: `cd app && uv run ruff check .` および `uv run ruff format --check .`
- 型チェック: `cd app && uv run mypy .`
- Docker: `docker build app --target runtime`
- 構造確認: リポジトリ直下の `tests/` が存在せず、`app/tests/` に全28ファイルが存在することを確認する。

## リスクと対策

- **相対パスの破損**: `Path(__file__)` の親階層が変わり、`app/app` を参照する可能性がある。
  - 対策: 対象4ファイルを明示的に修正し、subprocess・Alembic を含む全テストを実行する。
- **import の衝突**: `tests` という一般的なパッケージ名が外部 package と衝突する可能性がある。
  - 対策: pytest の `pythonpath` を `app/` 自身に限定し、`cd app` で `tests.factories` の import を検証する。
- **coverage の意味変化**: `source = ["."]` に移動後のテストが含まれる。
  - 対策: `tests/*` を明示的に omit し、アプリケーションコードの coverage 指標を維持する。
- **本番 image の肥大化**: `COPY . ./` によりテストが runtime image に入る。
  - 対策: `app/.dockerignore` で `tests/` を除外し、image build を確認する。
- **履歴文書の不整合に見える記載**: 過去の計画・ログには旧パスが残る。
  - 対策: 過去時点の事実を保持するため変更せず、新しい計画・作業ログで移行を記録する。

## 成功基準・完了条件

- [ ] リポジトリ直下の `tests/` がなく、全28ファイルが `app/tests/` に移動している。
- [ ] `cd app && uv run pytest -c pyproject.toml` が失敗0件で完了する。
- [ ] branch coverage が移動前の計測対象を維持し、テストコードを計測していない。
- [ ] `cd app && uv run ruff check .`、`ruff format --check .`、`mypy .` がすべて成功する。
- [ ] 本番 runtime Docker image の build が成功し、`tests/` が image に含まれない。
- [ ] 現行のプロジェクト構成・テストルールが `app/tests/` を指している。
