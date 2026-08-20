# 実装計画: アプリケーションソースの `app/web_practice/` パッケージへの移行

## 概要

`app/` 直下にあるFastAPIアプリケーションソース全22ファイルを、`app/web_practice/` へディレクトリ構造を維持して移動し、正規のPythonパッケージとして構成する。`app/alembic/` は現位置に維持し、アプリケーション、テスト、Alembicからのimportを `web_practice.*` に統一する。

## 修正要件

- 移動先は `app/web_practice/` とする。
- `app/alembic/` は移動せず、`app/alembic.ini` とともに現位置へ維持する。
- `app/dependencies/`、`app/models/`、`app/routers/`、`app/schemas/`、`app/services/`、`app/config.py`、`app/database.py`、`app/main.py` を移動する。
- `app/web_practice/__init__.py` を追加し、`web_practice` をPythonパッケージとして定義する。
- アプリケーション内部、テスト、Alembic `env.py` のflat importを `web_practice.*` に更新する。
- `app/tests/` と設定・依存ファイルは `app/` 直下に維持する。
- Docker runtime のentry pointを `web_practice.main:app` に変更する。
- 過去の `docs/plans/` と `docs/logs/` は履歴資料として変更しない。

## 移行対象の調査結果

### 移動する既存ソース

修正後のユーザー指定対象は、Alembicを除く現在の実行時アプリケーションソース全22ファイルを網羅している。追加で移動すべき既存ファイルまたはディレクトリはない。

| 移動元 | 移動先 |
| --- | --- |
| `app/dependencies/**` | `app/web_practice/dependencies/**` |
| `app/models/**` | `app/web_practice/models/**` |
| `app/routers/**` | `app/web_practice/routers/**` |
| `app/schemas/**` | `app/web_practice/schemas/**` |
| `app/services/**` | `app/web_practice/services/**` |
| `app/config.py` | `app/web_practice/config.py` |
| `app/database.py` | `app/web_practice/database.py` |
| `app/main.py` | `app/web_practice/main.py` |

### 新規追加

| ファイル | 目的 |
| --- | --- |
| `app/web_practice/__init__.py` | `web_practice` をimport可能なPythonパッケージとして定義 |

### 移動せず残すもの

- Migration: `app/alembic/`
- Migration設定: `app/alembic.ini`
- テスト: `app/tests/`
- プロジェクト設定: `app/pyproject.toml`、`app/Dockerfile`、`app/.dockerignore`
- 依存ロック: `app/uv.lock`
- 生成物: `__pycache__/`、`.coverage`、各tool cache（Git管理外）

`app/alembic/env.py` は移動しないが、model metadataを新パッケージから取得するためimportのみ更新する。Migration pathが変わらないため、`app/alembic.ini` と `docs/dev-commandlist.md` のパス変更は不要である。

## パッケージ設計

- `app/` をpackage parent/source root、`app/web_practice/` をアプリケーションpackageとする。
- アプリケーション内部のimportは `from web_practice...` に統一し、同名の外部top-level packageとの衝突を防ぐ。
- pytestは既存の `pythonpath = ["."]` により `web_practice` と `tests` の双方を解決する。
- Uvicornは `/app` から `web_practice.main:app` をimportする。
- Alembicは既存の `prepend_sys_path = .` により、`alembic/env.py` から `web_practice.models` を解決する。

## 影響範囲

| ファイルパス | 変更種別 | 変更内容の概要 |
| --- | --- | --- |
| 上記22ソースファイル | 移動・修正 | `app/web_practice/` へ移動し、内部importをpackage-qualified形式へ変更 |
| `app/web_practice/__init__.py` | 新規 | アプリケーションpackageを定義 |
| `app/alembic/env.py` | 修正 | model、config、Baseのimportを `web_practice.*` に変更 |
| `app/Dockerfile` | 修正 | Uvicorn entry pointを `web_practice.main:app` に変更 |
| `app/pyproject.toml` | 修正 | coverage sourceを `web_practice` に変更し、新packageのみを計測 |
| `app/tests/conftest.py` | 修正 | fixture bootstrapのimportを `web_practice.*` に変更 |
| `app/tests/test_config.py` | 修正 | `config.py` の実ファイルパスを更新 |
| `app/tests/test_database.py` | 修正 | database importとsubprocess内importを更新 |
| `app/tests/test_main.py` | 修正 | main importを更新 |
| `app/tests/{dependencies,factories,models,routers,schemas,services}/**` | 修正 | 対象moduleのimportを `web_practice.*` に更新 |
| `README.md` | 修正 | Architecture treeとData Flowをpackage構成へ更新 |
| `CLAUDE.md`（`AGENTS.md` のリンク先） | 修正 | ソースコード位置とテストのミラー元を更新 |
| `.claude/rules/python-testing.md` | 修正 | coverage例を `web_practice` に更新 |

## 変更不要と判断した関連ファイル

| ファイルパス | 理由 |
| --- | --- |
| `app/alembic.ini` | `script_location = %(here)s/alembic` と `prepend_sys_path = .` を維持できる |
| `docs/dev-commandlist.md` | Migration directoryが移動しないため既存コマンドがそのまま有効 |
| `.vscode/settings.json` | 既存 `python.analysis.extraPaths = ["app"]` がpackage parentを正しく指す |
| `app/.dockerignore` | `tests/` の位置は変わらず、既存除外設定が有効 |
| `app/uv.lock` | 依存関係とproject metadataに変更がない |
| `compose.yaml`、`Caddyfile` | build context、service名、portに変更がない |
| ルート `Dockerfile`、`.devcontainer/post-create.sh` | `app/pyproject.toml` の位置が変わらない |

## 実装ステップ

### フェーズ1: 回帰基準の確認とpackage作成

1. **移動前の回帰基準確認** - (対象: `app/`, `app/tests/`)
   - アクション: 全pytest、coverage、Ruff check、Ruff format check、mypy、Alembic graph/offline SQLを実行し、現行結果を記録する。
   - 理由: package化の前後でアプリケーションの振る舞いが変わっていないことを比較するため。
   - 依存関係: なし。
   - リスク: 低。専用PostgreSQL URL未設定時の既存1件skipは許容する。

2. **アプリケーションソースの移動** - (対象: 上記22ファイル、`app/web_practice/__init__.py`)
   - アクション: 既存構造を維持して `app/web_practice/` へGit renameし、package rootの `__init__.py` を追加する。
   - 理由: テスト・Migration・設定とアプリケーションpackageを明確に分離するため。
   - 依存関係: ステップ1。
   - リスク: 中。すべてのimport元からmodule pathが変わる。

### フェーズ2: importと実行設定の更新

3. **アプリケーション内部importの更新** - (対象: `app/web_practice/**/*.py`)
   - アクション: `config`、`database`、`dependencies`、`models`、`routers`、`schemas`、`services` のimportへ `web_practice.` prefixを追加する。
   - 理由: 正規packageとしてimport経路を一意にし、top-level module依存を解消するため。
   - 依存関係: ステップ2。
   - リスク: 高。循環importの初期化順を既存と同じ順序に保つ必要がある。

4. **Alembic importの更新** - (ファイル: `app/alembic/env.py`)
   - アクション: `models`、`config`、`database` のimportを `web_practice.*` に変更する。
   - 理由: Migrationを現位置に保ったまま、新packageのmetadataとDB設定を使用するため。
   - 依存関係: ステップ2、3。
   - リスク: 高。失敗するとautogenerate、upgrade、downgradeが実行不能になる。

5. **テストimportと実ファイルパスの更新** - (対象: `app/tests/**/*.py`)
   - アクション: アプリケーションmoduleのimportを `web_practice.*` に更新し、`CONFIG_PATH` とdatabase subprocess importを新packageへ合わせる。`tests.factories` のimportは維持する。
   - 理由: テストが公開されたpackage経路と実ファイル位置の両方を検証するため。
   - 依存関係: ステップ2、3。
   - リスク: 高。conftestは全133テストのimport前提を担い、subprocess testは別interpreterで経路を再構成する。

6. **Docker entry pointとcoverage設定の更新** - (ファイル: `app/Dockerfile`, `app/pyproject.toml`)
   - アクション: CMDを `uvicorn web_practice.main:app ...` に変更し、coverage `source` を `web_practice` に設定する。pytest `pythonpath`、Ruff、mypy、Pyrightの既存設定は維持する。
   - 理由: runtimeとcoverageが新packageを直接対象にするため。
   - 依存関係: ステップ2、3。
   - リスク: 高。entry pointの指定ミスはコンテナ起動失敗につながる。

### フェーズ3: 現行ドキュメントの更新

7. **構成説明と開発ルールの更新** - (ファイル: `README.md`, `CLAUDE.md`, `.claude/rules/python-testing.md`)
   - アクション: Architecture、Data Flow、source path、coverage commandを `app/web_practice/` 基準へ変更する。
   - 理由: 今後の実装とテストが新package構成に従うよう共有するため。
   - 依存関係: ステップ2。
   - リスク: 低。

### フェーズ4: 回帰検証

8. **テスト・静的検査・entry point検証** - (対象: `app/`, `app/web_practice/`, `app/alembic/`, `app/tests/`)
   - アクション: pytest、`--cov=web_practice` branch coverage、Ruff check/format、mypy、Alembic graph/offline SQL、Uvicorn package import/startup、構造確認、旧flat import検索、差分チェックを実行する。Docker CLIが利用可能ならruntime image buildとhealth checkも実行する。
   - 理由: package import、通常実行、Migration、テスト、静的解析の全経路が正常であることを確認するため。
   - 依存関係: ステップ2〜7。
   - リスク: 高。Docker CLIがない現在の環境ではimage buildを実行できない可能性があるため、その場合はUvicornの同等コマンドとDockerfileの静的レビューで補完し、未検証項目を明記する。

## テスト戦略

- 回帰テスト: `cd app && uv run pytest -c pyproject.toml`
- ユニットテスト: `cd app && uv run pytest -c pyproject.toml -m unit`
- 統合テスト: `cd app && uv run pytest -c pyproject.toml -m integration`
- Coverage: `cd app && uv run pytest -c pyproject.toml --cov=web_practice --cov-branch --cov-report=term-missing`
- Lint/Format: `cd app && uv run ruff check .`、`uv run ruff format --check .`
- 型チェック: `cd app && uv run mypy .`
- Alembic: `cd app && uv run alembic -c alembic.ini heads` とMigration offline SQL test
- Uvicorn: テスト用SQLite環境で `cd app && uv run uvicorn web_practice.main:app ...` の起動とshutdownを確認
- Docker: 利用可能な場合は `docker build app --target runtime` とimage内のhealth endpointを確認
- 構造確認: 旧source pathsがなく、`app/web_practice/` に既存22ファイルと新規 `__init__.py` が存在し、`app/alembic/` が現位置に維持されていることを確認

## リスクと対策

- **循環importの変化**: package-qualified importによりpackage初期化の順序が変わる可能性がある。
  - 対策: 各 `__init__.py` のexport順を維持し、全module importと全テストで検証する。
- **Alembic実行不能**: `env.py` が旧top-level moduleを参照するとmetadataを取得できない。
  - 対策: `web_practice.*` importへ更新し、revision graph、offline SQL、upgrade/downgrade testで検証する。
- **コンテナ起動不能**: `/app/main.py` がなくなるため従来のCMDではimportできない。
  - 対策: `web_practice.main:app` を指定し、Uvicorn startupとDockerfileレビューを実施する。
- **テストimport不能**: テストに旧flat importが残る可能性がある。
  - 対策: `rg` で旧importを検出し、subprocessを含む全133テストを実行する。
- **coverage指標の変化**: source patternが新packageと一致しない可能性がある。
  - 対策: `--cov=web_practice` で310 statements・30 branchesの既存基準と比較する。
- **Migrationの誤移動**: 一括移動時に `app/alembic/` を含める可能性がある。
  - 対策: 移動対象を明示的な8パスに限定し、構造確認で `app/alembic/` の全10ファイルを確認する。

## 成功基準・完了条件

- [ ] 指定された全22ソースファイルが `app/web_practice/` に移動し、旧source pathsが存在しない。
- [ ] `app/web_practice/__init__.py` が追加され、`web_practice` packageとしてimportできる。
- [ ] `app/alembic/` と `app/alembic.ini` が移動されず、Migrationが正常に動作する。
- [ ] アプリケーション、テスト、Alembicに旧flat importが残っていない。
- [ ] 全133テストが移動前と同じ結果（132 passed、1 skipped）で完了する。
- [ ] branch coverageが100%を維持する。
- [ ] Ruff check、Ruff format check、mypy、Alembic graph/offline SQL、Uvicorn startupが成功する。
- [ ] Docker CLIが利用可能な場合はruntime image buildとhealth checkが成功する。利用不可の場合は未検証理由を記録する。
- [ ] READMEと開発ルールが新しいpackage pathを指している。
