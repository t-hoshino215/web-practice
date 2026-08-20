# 実装計画: Python テストスイート

## 概要

`app/` 配下の FastAPI アプリケーションに対し、現在 0 件の pytest テストを新規作成する。`tests/` は `app/` の構造をミラーし、認証・CSRF・所有権・入力検証・DB 制約・Cookie・Migration を正常系と異常系の両方から検証する。

通常のテストは外部サービスなしで再現可能にし、PostgreSQL 固有の Migration は、誤って本番 DB を変更しないよう明示的な専用 `TEST_DATABASE_URL` がある場合だけ実行する。

## 要件

- pytest を使用し、`unit` / `integration` marker で分類する。
- `tests/` 配下に `app/` のディレクトリ構造をミラーする。
- AAA パターン、原則 1 assertion、境界値の `parametrize`、共有 fixture、factory パターンを採用する。
- FastAPI の HTTP 契約、SQLAlchemy の永続化と制約、認証・CSRF の失敗分岐を検証する。
- テスト import 前にテスト用 `DATABASE_URL` を設定し、本番 DB へ接続しない。
- SQLite の timezone 差異は認証 Dependency の mock と dependency override で隔離する。
- PostgreSQL Migration テストは専用テスト DB だけを許可し、未設定時は安全に skip する。
- 実装コードは、テストによって不具合が判明しない限り変更しない。
- pytest、coverage、ruff、mypy がすべて成功してから完了とする。

## 影響範囲

| ファイルパス | 変更種別 | 変更内容の概要 |
| --- | --- | --- |
| `app/pyproject.toml` | 修正 | `httpx`、pytest の探索先、テスト実行設定を追加 |
| `app/uv.lock` | 修正 | 開発依存関係の lock を更新 |
| `tests/__init__.py` | 新規 | テストパッケージを定義 |
| `tests/conftest.py` | 新規 | 環境変数、SQLite、Session、FastAPI client、認証 override の fixture を定義 |
| `tests/factories/__init__.py` | 新規 | factory helper を公開 |
| `tests/factories/models.py` | 新規 | User、AuthSession、Message のテストデータ factory を定義 |
| `tests/test_config.py` | 新規 | 環境変数と Cookie Secure 設定を検証 |
| `tests/test_database.py` | 新規 | DB Session の生成と確実な close を検証 |
| `tests/test_main.py` | 新規 | route 登録と lifespan の engine dispose を検証 |
| `tests/services/__init__.py` | 新規 | service テストパッケージを定義 |
| `tests/services/test_auth.py` | 新規 | パスワード、Session/CSRF token、期限、username 正規化を検証 |
| `tests/schemas/__init__.py` | 新規 | schema テストパッケージを定義 |
| `tests/schemas/test_user.py` | 新規 | User schema の境界値、pattern、ORM 変換を検証 |
| `tests/schemas/test_auth.py` | 新規 | Login schema の境界値と response 構造を検証 |
| `tests/schemas/test_message.py` | 新規 | Message schema の境界値と ORM 変換を検証 |
| `tests/models/__init__.py` | 新規 | model テストパッケージを定義 |
| `tests/models/test_user.py` | 新規 | User の default、unique、role CHECK 制約を検証 |
| `tests/models/test_auth_session.py` | 新規 | AuthSession の必須値、token unique、cascade を検証 |
| `tests/models/test_message.py` | 新規 | Message の default、owner 必須、cascade を検証 |
| `tests/dependencies/__init__.py` | 新規 | dependency テストパッケージを定義 |
| `tests/dependencies/test_auth.py` | 新規 | Cookie なし、不明・期限切れ Session、orphan user、権限を検証 |
| `tests/dependencies/test_csrf.py` | 新規 | CSRF header の未指定、不一致、一致を検証 |
| `tests/routers/__init__.py` | 新規 | router テストパッケージを定義 |
| `tests/routers/test_health.py` | 新規 | root、health、DB health endpoint を検証 |
| `tests/routers/test_users.py` | 新規 | 登録、重複、rollback、入力検証、`/users/me` を検証 |
| `tests/routers/test_auth.py` | 新規 | login、Cookie 属性、認証失敗、logout、CSRF を検証 |
| `tests/routers/test_messages.py` | 新規 | 所有者別一覧、作成、archive、404、認証・CSRF を検証 |
| `tests/routers/test_admin.py` | 新規 | 管理者一覧、一般ユーザー 403、未認証 401 を検証 |
| `tests/alembic/__init__.py` | 新規 | Migration テストパッケージを定義 |
| `tests/alembic/test_migrations.py` | 新規 | revision chain と専用 PostgreSQL 上の upgrade/downgrade を検証 |

## 実装ステップ

### フェーズ1: テスト基盤

1. **テスト依存関係と pytest 設定の追加** - (ファイル: `app/pyproject.toml`, `app/uv.lock`)
   - アクション: FastAPI `TestClient` 用の `httpx` を開発依存に追加し、`cd app && uv run pytest` で `../tests` を探索できるよう設定する。
   - 理由: 現在は API 統合テストの依存とテスト探索設定がないため。
   - 依存関係: なし
   - リスク: 低

2. **共通 fixture と factory の作成** - (ファイル: `tests/conftest.py`, `tests/factories/models.py`)
   - アクション: import 前の環境変数、外部接続しない SQLite engine、外部キー有効化、Session、テスト DB 初期化、`get_db` override、TestClient、User/AuthSession/Message factory を実装する。
   - 理由: 各テストを独立させ、本番 DB やテスト順序への依存をなくすため。
   - 依存関係: ステップ1が必要
   - リスク: 中（SQLite と PostgreSQL の挙動差）

### フェーズ2: 単体テスト

3. **設定・DB・アプリ生成のテスト** - (ファイル: `tests/test_config.py`, `tests/test_database.py`, `tests/test_main.py`)
   - アクション: `DATABASE_URL`、`COOKIE_SECURE` の真偽値、`get_db()` の正常/例外終了時 close、全 route 登録、lifespan shutdown 時の dispose を検証する。
   - 理由: import とアプリ起動の基盤動作を保証するため。
   - 依存関係: ステップ2が必要
   - リスク: 中（config reload が他テストへ影響しないよう module state の復元が必要）

4. **認証 service のテスト** - (ファイル: `tests/services/test_auth.py`)
   - アクション: password hash/verify、Session/CSRF token の生成と SHA-256、CSRF 一致/不一致、UTC の期限、username 正規化を検証する。
   - 理由: 認証の純粋ロジックとセキュリティ上重要な変換を高速に網羅するため。
   - 依存関係: ステップ2が必要
   - リスク: 低（乱数値や Argon2 hash 文字列そのものには依存しない）

5. **Pydantic schema のテスト** - (ファイル: `tests/schemas/test_user.py`, `tests/schemas/test_auth.py`, `tests/schemas/test_message.py`)
   - アクション: min/max 境界、username pattern、無効 payload、ORM attributes からの response 変換、秘密情報が response に含まれないことを検証する。
   - 理由: API 境界で不正入力を拒否する契約を保証するため。
   - 依存関係: ステップ2が必要
   - リスク: 低

6. **認証・CSRF Dependency のテスト** - (ファイル: `tests/dependencies/test_auth.py`, `tests/dependencies/test_csrf.py`)
   - アクション: Session Cookie の未指定、不明 token、期限切れ削除、存在しない user の Session 削除、有効 user、admin 許可/拒否、CSRF 未指定/不一致/一致を mock Session と aware UTC datetime で検証する。
   - 理由: HTTP endpoint から共有される 401/403 と cleanup 分岐を漏れなく保証するため。
   - 依存関係: ステップ4が必要
   - リスク: 中（SQLAlchemy Session mock の呼び出し契約を実装と一致させる必要）

### フェーズ3: DB・API 統合テスト

7. **SQLAlchemy model のテスト** - (ファイル: `tests/models/test_user.py`, `tests/models/test_auth_session.py`, `tests/models/test_message.py`)
   - アクション: default 値、unique/CHECK/NOT NULL、外部キー、User 削除時 cascade を SQLite 上で検証する。
   - 理由: ORM metadata と主要 DB 制約の退行を検出するため。
   - 依存関係: ステップ2が必要
   - リスク: 中（PostgreSQL 固有の型・DDL 検証は Migration テストへ分離）

8. **公開・ユーザー・認証 endpoint のテスト** - (ファイル: `tests/routers/test_health.py`, `tests/routers/test_users.py`, `tests/routers/test_auth.py`)
   - アクション: root/health/DB health、ユーザー登録と重複 race、入力 422、現在ユーザー、login 成否、Session/CSRF 保存、Cookie 属性、logout と Cookie 削除を HTTP 経由で検証する。
   - 理由: response model、status、header/Cookie、DB 操作を含む API 契約を保証するため。
   - 依存関係: ステップ2、4、5、6、7が必要
   - リスク: 中（timezone の差異がある認証 Session 取得は dependency override で隔離）

9. **メッセージ・管理者 endpoint のテスト** - (ファイル: `tests/routers/test_messages.py`, `tests/routers/test_admin.py`)
   - アクション: 自分の Message だけの一覧、作成 owner、archive、他人の Message を隠す 404、CSRF、admin 全件一覧、一般 user 403、未認証 401 を検証する。
   - 理由: データ分離、所有権、権限境界の退行を防ぐため。
   - 依存関係: ステップ2、5、6、7が必要
   - リスク: 中

10. **Alembic Migration のテスト** - (ファイル: `tests/alembic/test_migrations.py`)
    - アクション: 常時実行する revision chain/single head の検証と、安全条件を満たす `TEST_DATABASE_URL` が指定された場合の clean DB `upgrade head`、schema inspection、`downgrade base` を実装する。
    - 理由: Migration の欠落・分岐と PostgreSQL 上の DDL を検証するため。
    - 依存関係: ステップ1が必要
    - リスク: 高（破壊的 DDL のため、通常 `DATABASE_URL` は禁止し、テスト専用 DB 名を検証する）

### フェーズ4: 品質検証

11. **全テストと静的検査の実行** - (ファイル: 変更ファイル全体)
    - アクション: `uv sync --locked --dev` で壊れている既存 `.venv` を同期し、pytest、branch coverage、ruff check、ruff format check、mypy を実行する。失敗時はテスト設計または判明した実装不具合を最小変更で修正して再実行する。
    - 理由: 検証後にのみ完了とするリポジトリ原則を満たすため。
    - 依存関係: ステップ3〜10が必要
    - リスク: 中（テストが既存実装の不具合を顕在化させる可能性）

## テスト戦略

- ユニットテスト: `config.py`、`database.py`、`main.py`、`services/auth.py`、`dependencies/auth.py`、`dependencies/csrf.py`、各 Pydantic schema。
- 統合テスト: SQLite 上の各 SQLAlchemy model と、dependency override を利用した全 FastAPI endpoint。PostgreSQL 専用 DB が明示された場合は Alembic upgrade/downgrade。
- E2Eテスト: 今回はブラウザー/Caddy/Compose を対象外とする。TestClient 上で登録、login、認証済み操作、logout の HTTP 契約を個別に検証する。
- 想定件数: 約 70〜80 ケース。境界値は `parametrize` にまとめる。
- 検証コマンド（`app/pyproject.toml` を常に明示して marker・探索設定を有効にする）:
  - `cd app && uv run pytest -c pyproject.toml`
  - `cd app && uv run pytest -c pyproject.toml --cov=. --cov-branch --cov-report=term-missing`
  - `cd app && uv run ruff check . ../tests`
  - `cd app && uv run ruff format --check . ../tests`
  - `cd app && uv run mypy . ../tests`

## リスクと対策

- **本番 DB の誤更新**: Migration テストは schema を作成・削除する。
  - 対策: `DATABASE_URL` を流用せず、明示的な `TEST_DATABASE_URL` とテスト専用 DB 名の安全チェックを必須にする。未指定時は PostgreSQL DDL テストだけを skip する。
- **SQLite と PostgreSQL の差異**: timezone、VARCHAR 長、DDL、外部キーの標準挙動が異なる。
  - 対策: aware datetime を使う Dependency 単体テスト、SQLite の外部キー有効化、schema validation、任意の PostgreSQL Migration 統合テストへ責務を分ける。
- **import 時の外部接続設定**: `config.py` は `DATABASE_URL` 未設定で import に失敗する。
  - 対策: `conftest.py` のアプリ import より前にテスト専用 URL を設定する。
- **config reload の副作用**: 環境変数別テストが他モジュールの定数へ影響し得る。
  - 対策: 分離 import または module state の確実な復元を行う。
- **既存 Migration のデータ移行不足**: `csrf_token_hash` と `messages.user_id` は既存行がある DB への NOT NULL 追加に backfill がない。
  - 対策: 今回は clean DB の migration を基準とし、既存データ migration の失敗が確認された場合はテスト結果に明記して別途データ移行方針を求める。
- **壊れた既存仮想環境**: 現在の `app/.venv` は旧 host の shebang を参照している。
  - 対策: lockfile 更新後に `uv sync --locked --dev` で再同期してから検証する。

## 成功基準・完了条件

- [ ] `tests/` が `app/` の主要実行時構造をミラーし、fixture と factory が共通化されている。
- [ ] 認証・CSRF・Cookie・所有権・権限・入力境界・DB 制約の正常系と異常系がテストされている。
- [ ] Alembic revision chain が常時検証され、専用 PostgreSQL URL がある環境では upgrade/downgrade が検証できる。
- [ ] `cd app && uv run pytest -c pyproject.toml` が失敗 0 件で完了する。
- [ ] branch coverage の未検証箇所を確認し、重要な分岐に抜けがない。
- [ ] ruff check、ruff format check、mypy がすべて成功する。
- [ ] 既存アプリコードへの変更は、テストで確認された不具合修正に限定される。
