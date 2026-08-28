# 作業ログ

## 1. 概要

| 項目 | 内容 |
| ----------- | ------ |
| 日付 | 2026-08-28 |
| タスク | Double Submit Cookie方式によるCSRFトークン再発行の実装とSTEP 10ドキュメント更新 |
| ステータス | 完了 |
| 関連ドキュメント | `docs/plans/20260828-150020_double-submit-csrf-refresh.md` |

## 2. 作業サマリー

Session Cookieに紐づくCSRFトークンを、JavaScriptから読めるCookieとリクエストヘッダーの両方で送るDouble Submit Cookie方式へ移行した。バックエンドではヘッダー・Cookie・DB保存ハッシュの3者を照合し、認証済みセッション向けの再発行APIを追加した。Reactフロントエンドは`sessionStorage`を廃止してCookieを正本とし、Cookie欠落時だけ再発行して認証状態を復元する。README、開発者向け構成説明、STEP 10ガイド、疎通確認手順も実装後の仕様へ更新した。

## 3. 変更内容

### コミット履歴

| コミット | メッセージ | 変更ファイル数 |
| --------- | ---------- | ------------- |
| `be09788` | feat(auth): add double submit CSRF cookies | 7 files |
| `7212972` | feat(frontend): use CSRF cookie as token source | 8 files |
| `efc78b1` | docs(step10): document CSRF cookie refresh | 4 files |
| `33151c0` | docs(step10): record documentation commit | 1 file |
| `0e6d831` | docs(plan): normalize trailing newline | 1 file |
| `b3cce3f` | fix(auth): reject non-ASCII CSRF tokens safely | 3 files |

### 対象外の未コミット変更

| 状態 | ファイルパス | 取り扱い |
| ---- | ------------ | -------- |
| 変更あり | `README.md` | ユーザーの並行作業として、本ログの対象・コミットから除外 |
| 未追跡 | `docs/guides/step11-cicd-github-actions.md` | ユーザーの並行作業として、本ログの対象・コミットから除外 |

### 変更ファイル一覧

| カテゴリ | ファイルパス | 変更種別 | 概要 |
| --------- | ------------ | --------- | ------ |
| ソースコード | `backend/src/web_practice/config.py` | 修正 | CSRF Cookie名の設定を追加 |
| ソースコード | `backend/src/web_practice/dependencies/csrf.py` | 修正 | ヘッダー・Cookie・セッションハッシュの3者照合と非ASCII入力の安全な比較を実装 |
| ソースコード | `backend/src/web_practice/routers/auth.py` | 修正 | ログイン時のCSRF Cookie発行、再発行API、ログアウト時の両Cookie削除を追加 |
| ソースコード | `frontend/src/api/client.ts` | 修正 | `sessionStorage`を廃止し、CookieからCSRFトークンを取得して送信する処理へ変更 |
| ソースコード | `frontend/src/api/auth.ts` | 修正 | CSRFトークンの保存処理を削除し、再発行API呼び出しを追加 |
| ソースコード | `frontend/src/hooks/useAuth.ts` | 修正 | 認証復元時にCookie欠落の場合だけCSRFトークンを再発行 |
| テスト | `backend/tests/dependencies/test_csrf.py` | 修正 | 3者照合、欠落・不一致、非ASCII入力のテストを追加・更新 |
| テスト | `backend/tests/routers/test_auth.py` | 修正 | Cookie属性、再発行、旧トークン無効化、新トークン受理、ログアウト時削除を検証 |
| テスト | `backend/tests/routers/test_messages.py` | 修正 | 状態変更APIでCSRF Cookieも必須になる契約を検証 |
| テスト | `frontend/src/api/client.test.ts` | 修正 | Cookie読取、Cookie名完全一致、不正エンコード、ヘッダー設定を検証 |
| テスト | `frontend/src/api/auth.test.ts` | 新規 | CSRF再発行APIのHTTP契約を検証 |
| テスト | `frontend/src/hooks/useAuth.test.ts` | 新規 | Cookie有無と再発行成否による認証復元を検証 |
| テスト | `frontend/tests/setup.ts` | 修正 | テスト後にCSRF Cookieを削除する後処理へ変更 |
| 設定 | `frontend/eslint.config.js` | 修正 | 旧`sessionStorage`前提のコメントを現行構成へ更新 |
| ドキュメント | `README.md` | 修正 | React/Vite構成、開発コマンド、API、Double Submit Cookie仕様を反映 |
| ドキュメント | `CLAUDE.md` | 修正 | フロントエンドのソース・テスト配置を追記 |
| ドキュメント | `docs/guides/step10-react-vite.md` | 修正 | 10-13と発展課題を実装済みのCSRF再発行方式へ更新 |
| ドキュメント | `docs/healthcheck.md` | 修正 | Cookie jarを使ったCSRF抽出・再発行・ログアウト確認手順へ更新 |
| ドキュメント | `docs/plans/20260828-150020_double-submit-csrf-refresh.md` | 新規 | 承認済み実装計画を記録 |

### 変更の詳細

#### セッション束縛型Double Submit Cookie

- ログイン時に、Session Cookieと同じ有効期間・`Secure`・`SameSite=Lax`・`Path=/`を持つ、非`HttpOnly`のCSRF Cookieを発行した。
- 状態変更APIでは`X-CSRF-Token`ヘッダーとCSRF Cookieを定数時間比較し、一致した値が現在の認証セッションに保存されたハッシュとも一致する場合だけ許可するようにした。
- 外部入力に非ASCII文字が含まれても`compare_digest`が`TypeError`を送出しないよう、UTF-8 bytesへ変換して比較し、不正な値は403として扱うようにした。

#### CSRFトークン再発行

- 認証済みセッション向けに`POST /api/auth/csrf`を追加し、新しいトークンのハッシュをDBへ保存してCSRF Cookieを再発行するようにした。
- 再発行後は旧トークンによる状態変更が403、新トークンによる状態変更が成功することを統合テストで保証した。
- ログアウト時はSession CookieとCSRF Cookieの両方を削除するようにした。

#### ReactフロントエンドのCookie正本化

- `sessionStorage`へのCSRFトークン保存・削除を廃止し、状態変更リクエストの直前に`document.cookie`から現在値を読むようにした。
- 認証状態の復元では`/api/users/me`成功後、CSRF Cookieが欠落している場合だけ再発行APIを呼び、失敗した場合は匿名状態へ戻すようにした。
- TDDでは初回REDとしてバックエンド10件、フロントエンド5件の失敗を確認した。レビュー修正では非ASCII入力の1件がREDとなり、修正後はすべてGREENになった。

#### ドキュメントと配布経路の整合

- READMEとCLAUDEをReact/Viteの実構成へ更新し、STEP 9・10の状態とリンクを整理した。
- STEP 10ガイドとhealthcheckを、Cookie抽出、3者照合、再発行、Cookie削除、トレードオフを含む再現可能な手順へ更新した。
- 最終検証はバックエンド140 passed・1 skipped・coverage 100%、フロントエンド25 passedとなり、lint、変更対象format check、型チェック、production build、Compose設定検証、backend/CaddyのDocker buildも成功した。

## 4. 計画との対比

| 計画のステップ | ステータス | 備考 |
| ------------- | ---------- | ------ |
| フェーズ1: バックエンドのCSRF契約をテストで定義 | ✅ 完了 | 欠落・不一致・3者一致・再発行・Cookieライフサイクルをテスト化 |
| フェーズ2: バックエンドへDouble Submit Cookieを実装 | ✅ 完了 | レビューで判明した非ASCII入力も403へ修正 |
| フェーズ3: フロントエンドをCookie正本へ移行 | ✅ 完了 | Cookie解析、再発行API、認証復元のテストを追加 |
| フェーズ4: ドキュメントを現行実装へ更新 | ✅ 完了 | README、CLAUDE、STEP 10ガイド、healthcheckを更新 |
| 総合検証と導入記録 | ✅ 完了 | 自動検証とDocker buildに成功し、10-13のコミットを記録 |
| コードレビュー | ✅ 完了 | 初回MEDIUM 2件を修正し、再レビューでCRITICAL・HIGH・MEDIUMなし、APPROVE |

## 5. 技術的メモ

- 設計判断: 単純なDouble Submit CookieではなくDBのセッション保存ハッシュも照合し、CSRFトークンを現在の認証セッションへ束縛した。
- 設計判断: 再発行APIはCSRF Cookie欠落時のブートストラップ用途なのでCSRF Dependencyを付けず、`SameSite=Lax`のSession Cookieと同一サイト通信を前提にした。
- 設計判断: ログインレスポンスの`csrf_token`は既存クライアント互換のため維持したが、ReactフロントエンドではCookieを正本とした。
- セキュリティ: Pythonの`secrets.compare_digest(str, str)`は非ASCII文字で`TypeError`になるため、外部入力はUTF-8 bytesへ変換して比較する必要がある。
- 競合: 複数タブが同時に再発行すると最後のトークンだけが有効になる。Cookie欠落時だけ再発行し、状態変更の直前に共有Cookieを読むことで競合時間を狭めた。
- 依存関係: 新しいライブラリの追加はなし。

## 6. 残課題

| 課題 | 優先度 | 備考 |
| ------ | ------- | ------ |
| バックエンド全体のformat check | 低 | 今回未変更の`backend/src/web_practice/main.py`と`backend/tests/alembic/test_migrations.py`が既存未整形のため、リポジトリ全体の`ruff format --check .`のみ失敗する。今回の変更対象format checkは成功済み。 |
