# 実装計画: Double Submit Cookie による CSRF トークン再発行

## 概要

STEP 10 の任意課題として、`sessionStorage` に依存している CSRF トークン管理を、JavaScript から読める CSRF Cookie とリクエストヘッダーを照合する Double Submit Cookie 方式へ変更する。CSRF Cookie が欠落した場合だけ現在の認証セッションに紐づくトークンを再発行し、別タブや同一ホスト上の開発・本番ポート間でも再ログインせずに状態変更できるようにする。あわせて STEP 10 の実装内容に README、開発者向け規約、疎通確認手順、ガイド本文を整合させる。

## 要件

- ログイン時に Session Cookie に加え、同じ有効期間・`Secure`・`SameSite=Lax`・`Path=/` を持つ、`HttpOnly` ではない CSRF Cookie を発行する。
- 状態変更 API では `X-CSRF-Token` ヘッダー、CSRF Cookie、現在の認証セッションに保存された CSRF ハッシュの3者が一致した場合だけ処理を許可する。
- 認証済みセッションの CSRF Cookie が欠落した場合、`POST /api/auth/csrf` で新しいトークンを Cookie に設定し、DBのハッシュも更新する。
- フロントエンドは `sessionStorage` を使用せず、状態変更リクエストの直前に CSRF Cookieを読み取ってヘッダーへ設定する。
- 認証状態の復元時は、ユーザー取得成功後に CSRF Cookie が無い場合だけ再発行 API を呼び、成功後に認証済み状態へ遷移する。
- ログアウト時は Session Cookie と CSRF Cookie の両方を削除する。
- 既存クライアントとの互換性を保つため、ログインレスポンスの `csrf_token` は維持するが、React フロントエンドでは Cookie を正本として扱う。
- `README.md` と `CLAUDE.md` を 10-13 の指示どおり React/Vite 構成へ更新し、CSRF の現行仕様も記載する。
- `docs/guides/step10-react-vite.md` と `docs/healthcheck.md` のサンプル、確認項目、制約、トラブルシューティングを新方式へ整合させる。
- TDDで失敗するテストを先に追加し、バックエンドとフロントエンドの全品質チェックが成功するまで完了としない。

## 影響範囲

| ファイルパス | 変更種別 | 変更内容の概要 |
| --- | --- | --- |
| `backend/src/web_practice/config.py` | 修正 | CSRF Cookie 名を設定値として追加 |
| `backend/src/web_practice/routers/auth.py` | 修正 | ログイン時の CSRF Cookie 発行、再発行 API、ログアウト時の Cookie 削除を追加 |
| `backend/src/web_practice/dependencies/csrf.py` | 修正 | ヘッダー・Cookie・セッションハッシュの3者検証へ変更 |
| `backend/tests/dependencies/test_csrf.py` | 修正 | Cookie欠落、不一致、DBハッシュ不一致、正常系をTDDで追加・更新 |
| `backend/tests/routers/test_auth.py` | 修正 | Cookie属性、再発行、ローテーション、ログアウト時の削除を検証 |
| `backend/tests/routers/test_messages.py` | 修正 | 状態変更 API のテストを Double Submit Cookie 契約へ更新 |
| `frontend/src/api/client.ts` | 修正 | `sessionStorage` 管理を廃止し、Cookie読取とヘッダー設定へ変更 |
| `frontend/src/api/client.test.ts` | 修正 | Cookie読取、完全一致するCookie名、欠落時エラー、ヘッダー設定を検証 |
| `frontend/src/api/auth.ts` | 修正 | ログイン時の保存処理を廃止し、CSRF再発行 API 呼び出しを追加 |
| `frontend/src/api/auth.test.ts` | 新規 | CSRF再発行 API のHTTP契約を検証 |
| `frontend/src/hooks/useAuth.ts` | 修正 | Cookie欠落時に再発行して認証状態を復元する処理へ変更 |
| `frontend/src/hooks/useAuth.test.ts` | 新規 | Cookie有無・再発行成功・失敗時の認証復元を検証 |
| `frontend/tests/setup.ts` | 修正 | テスト間で CSRF Cookie を消去する後処理へ変更 |
| `frontend/eslint.config.js` | 修正 | ブラウザAPIに関するコメントから旧 `sessionStorage` 前提を除去 |
| `README.md` | 修正 | Tech Stack、Runtime、frontend構成、開発コマンド、STEP、リンク、CSRF/API説明を更新 |
| `CLAUDE.md` | 修正 | frontendのソース、コロケーションテスト、共通テスト資材の配置を追記 |
| `docs/healthcheck.md` | 修正 | CSRF Cookieの保存・抽出・ヘッダー送信・削除確認へ更新 |
| `docs/guides/step10-react-vite.md` | 修正 | ガイド全体のコード例と説明を Double Submit Cookie に統一し、10-13と発展課題の導入記録を更新 |

## 実装ステップ

### フェーズ1: バックエンドの CSRF 契約をテストで定義

1. **Double Submit 検証のユニットテストを追加** - (ファイル: `backend/tests/dependencies/test_csrf.py`)
   - アクション: ヘッダー欠落、Cookie欠落、ヘッダーとCookieの不一致、両者一致だがDBハッシュ不一致、3者一致のケースを追加する。
   - 理由: Cookieを単に保存するだけでなく、Double Submit とセッション束縛が実際に強制されることを先に契約化するため。
   - 依存関係: なし。
   - リスク: 低。

2. **認証ルーターの Cookie・再発行テストを追加** - (ファイル: `backend/tests/routers/test_auth.py`)
   - アクション: ログインが非 `HttpOnly` の CSRF Cookie を適切な属性で設定すること、未認証の再発行が401になること、認証済み再発行が Cookie とDBハッシュを更新すること、旧トークンが拒否され新トークンが通ること、ログアウトが両Cookieを削除することを検証する。
   - 理由: ブラウザとの境界となるHTTP契約と、再発行後の安全なローテーションを保証するため。
   - 依存関係: ステップ1の契約を前提とする。
   - リスク: 中。複数の `Set-Cookie` は個別ヘッダーとして検証する必要がある。

3. **状態変更ルーターのテスト契約を更新** - (ファイル: `backend/tests/routers/test_messages.py`)
   - アクション: 認証ヘルパーに CSRF Cookie を設定し、ヘッダーのみ・Cookieのみ・不一致が拒否されることを必要な範囲で確認する。
   - 理由: Dependency の単体テストだけでなく実HTTP経路でも新契約が適用されることを保証するため。
   - 依存関係: ステップ1。
   - リスク: 低。

### フェーズ2: バックエンドへ Double Submit Cookie を実装

4. **Cookie設定と3者照合を実装** - (ファイル: `backend/src/web_practice/config.py`, `backend/src/web_practice/dependencies/csrf.py`)
   - アクション: `CSRF_COOKIE_NAME` を追加し、`require_csrf` でヘッダーとCookieを定数時間比較したうえで、既存のセッションハッシュ検証も行う。
   - 理由: Cookieを偽装・欠落させたリクエストと、現在のセッションに紐づかないトークンを拒否するため。
   - 依存関係: ステップ1、3。
   - リスク: 中。Cookie名とエラー分類を全経路で統一する必要がある。

5. **ログイン・再発行・ログアウトの Cookie ライフサイクルを実装** - (ファイル: `backend/src/web_practice/routers/auth.py`)
   - アクション: ログイン時に CSRF Cookie を設定し、認証必須の `POST /auth/csrf` で新トークンのハッシュをcommitしてCookieを返し、ログアウト成功時に両Cookieを同じ `Path` で削除する。再発行 API はレスポンスボディを持たない204とする。
   - 理由: 新規ログイン、Cookie欠落からの復元、ログアウトの全ライフサイクルを一貫させるため。
   - 依存関係: ステップ2、4。
   - リスク: 中。再発行 API はCSRFトークン取得前のブートストラップ用途なので `require_csrf` を付けず、`SameSite=Lax` の Session Cookie と同一オリジン通信を前提にすることを文書化する。

6. **バックエンドを段階検証** - (対象: `backend/`)
   - アクション: 対象pytest、全pytest、ruff、mypyを実行する。
   - 理由: 認証・Cookie契約の回帰と静的品質を確認するため。
   - 依存関係: ステップ4、5。
   - リスク: 低。

### フェーズ3: フロントエンドを Cookie 正本へ移行

7. **Cookie読取と再発行フローのテストを追加** - (ファイル: `frontend/src/api/client.test.ts`, `frontend/src/api/auth.test.ts`, `frontend/src/hooks/useAuth.test.ts`, `frontend/tests/setup.ts`)
   - アクション: `document.cookie` から対象名だけを安全に読むこと、Cookie欠落時は送信前エラーになること、再発行 API の呼び出し、復元時の条件付き再発行と失敗時の匿名化をテストする。テスト後は対象Cookieを明示的に期限切れにする。
   - 理由: タブ共有の前提となるCookie利用とブートストラップ分岐をTDDで固定するため。
   - 依存関係: バックエンドのAPI契約（ステップ5）。
   - リスク: 中。jsdomのCookie jarをテスト間で確実に隔離する必要がある。

8. **APIクライアントと認証復元を実装** - (ファイル: `frontend/src/api/client.ts`, `frontend/src/api/auth.ts`, `frontend/src/hooks/useAuth.ts`, `frontend/eslint.config.js`)
   - アクション: `sessionStorage` の取得・保存・削除関数を廃止し、Cookie名の完全一致とデコードを行う `getCsrfToken` に置き換える。ログインはレスポンス保存を行わず、認証復元では `/users/me` 成功かつCookie欠落時だけ再発行し、各状態変更の直前に共有Cookieからヘッダー値を取得する。
   - 理由: 別タブ・同一ホストの別ポートでも現在値を共有し、他タブでの再発行後も最新トークンを使えるようにするため。
   - 依存関係: ステップ7。
   - リスク: 中。不正な percent-encoding を含むCookieで例外にならないよう防御的に扱う。

9. **フロントエンドを段階検証** - (対象: `frontend/`)
   - アクション: 対象Vitest、全Vitest、coverage、typecheck、lint、format check、production buildを実行する。
   - 理由: DOM環境、型、Lint、実ビルドの各境界で回帰がないことを確認するため。
   - 依存関係: ステップ7、8。
   - リスク: 低。

### フェーズ4: ドキュメントを現行実装へ更新

10. **README と開発者向け構成説明を更新** - (ファイル: `README.md`, `CLAUDE.md`)
    - アクション: 10-13 の表に従ってフロントエンド技術、Caddyの静的配信/API振り分け、実際のディレクトリ構成、pnpmコマンド、STEP 9/10、STEP 9リンクを更新する。API節には CSRF Cookie、再発行エンドポイント、Double Submit の検証契約を反映する。
    - 理由: リポジトリの入口を現在の実装と一致させるため。
    - 依存関係: ステップ5、8。
    - リスク: 中。STEP 10の完了表記とガイドの導入記録を同時に整合させる必要がある。

11. **ガイドと疎通確認を Double Submit Cookie へ統一** - (ファイル: `docs/guides/step10-react-vite.md`, `docs/healthcheck.md`)
    - アクション: `sessionStorage` 前提のセットアップ、schema/API client/auth/useAuthコード例、DevTools確認、ポート間制約、トラブルシューティングを実装後のコードへ更新する。「発展」節はローテーション方式の提案から、採用したセッション束縛型 Double Submit Cookie のTDD手順・属性・再発行フロー・トレードオフ説明へ差し替える。curlではCookie jarからCSRF値を取り出し、Cookieとヘッダーを同時送信する手順に更新する。
    - 理由: 発展節だけを変更して本文と実装が矛盾する状態を避け、学習手順として再現可能にするため。
    - 依存関係: ステップ10。
    - リスク: 中。長いコード例と実ファイルの差異が生じやすいため、検索で旧 `sessionStorage` 前提の残存を確認する。

12. **総合検証と導入記録を更新** - (対象: リポジトリ全体)
    - アクション: バックエンド・フロントエンドの全検証を再実行し、必要に応じてDocker buildも確認する。ガイドの10-13と発展課題を完了へ更新し、実際のコミットハッシュは実装コミット後に記録する。
    - 理由: ドキュメントに記載したコマンドと成果物が実際に成立することを確認するため。
    - 依存関係: ステップ6、9、11。
    - リスク: 中。Docker検証はローカル環境の既存コンテナ状態に左右される可能性がある。

## テスト戦略

- ユニットテスト: `backend/tests/dependencies/test_csrf.py` で3者照合、`frontend/src/api/client.test.ts` でCookie解析とヘッダー生成を検証する。
- 統合テスト: `backend/tests/routers/test_auth.py` でログイン・再発行・ログアウトのCookieライフサイクル、`backend/tests/routers/test_messages.py` で状態変更APIへの適用、`frontend/src/api/auth.test.ts` と `frontend/src/hooks/useAuth.test.ts` でHTTP呼び出しと認証復元を検証する。
- E2E相当の手動確認: 同一ホストの別タブ、および `localhost:5173` と `localhost:80` で Session/CSRF Cookieが共有され、状態変更が成功することをDevToolsと `docs/healthcheck.md` のcurl手順で確認する。
- 品質チェック: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`, `pnpm test`, `pnpm test:coverage`, `pnpm typecheck`, `pnpm lint`, `pnpm format:check`, `pnpm build` を実行する。

## リスクと対策

- **CSRF Cookie の書換え**: 読み取り可能Cookieだけを信用すると攻撃者が値を差し替えられる可能性がある。
  - 対策: ヘッダーとCookieの一致だけでなく、認証セッションに保存済みのハッシュとも照合する。
- **再発行の競合**: 複数タブが同時に再発行すると、一時的に古いトークンが無効になる。
  - 対策: Cookie欠落時だけ再発行し、状態変更リクエストは送信直前に共有Cookieを読む。競合ケースもテスト可能な範囲で確認する。
- **Cookie属性・削除条件の不一致**: 発行時と削除時の名前や `Path` が異なるとブラウザにCookieが残る。
  - 対策: 定数と共通の属性を用い、ログアウトレスポンスをテストする。
- **`Secure` Cookie のローカル検証**: `COOKIE_SECURE=true` のCookieはHTTPでは送信されない。
  - 対策: ローカルは既存どおりfalse、公開HTTPS環境はtrueとし、両設定のレスポンス属性をテストする。
- **XSSとの境界**: CSRF CookieはJavaScriptから読むため、XSSに対する秘密情報にはならない。
  - 対策: Session Cookieの `HttpOnly` は維持し、Double Submit CookieがCSRF対策でありXSS対策ではないことをガイドに明記する。
- **ガイドと実装の不整合**: STEP 10本文には `sessionStorage` 前提の例が複数存在する。
  - 対策: 全文検索で旧キー、旧関数、旧制約の残存を洗い出し、実ファイルとの差分をレビューする。
- **ログインレスポンスの重複**: CookieとJSONの双方で生トークンを返す状態になる。
  - 対策: 互換性のため今回はレスポンスフィールドを維持し、フロントエンドと文書ではCookieを正本と明示する。将来の破壊的API整理として分離する。

## 成功基準・完了条件

- [ ] ログイン時に `session` は `HttpOnly`、CSRF Cookieは非 `HttpOnly` で、両方に適切な `Secure`・`SameSite=Lax`・`Path=/`・有効期間が設定される。
- [ ] 状態変更APIはヘッダー・CSRF Cookie・セッションハッシュのいずれかが欠落または不一致なら403を返す。
- [ ] 認証済みでCSRF Cookieが無い場合、再発行APIがCookieとDBハッシュを更新し、その後の状態変更が成功する。
- [ ] 未認証の再発行APIは401を返し、ログアウトはSession/CSRF Cookieを両方削除する。
- [ ] Reactフロントエンドに `sessionStorage` ベースのCSRF保持が残らず、別タブ・同一ホストの別ポートでCookieを共有できる。
- [ ] 認証状態復元でCookie欠落時だけ再発行し、成功時は認証済み、失敗時は安全に匿名状態となる。
- [ ] README、CLAUDE、STEP 10ガイド、healthcheckが実装後の構成と手順に一致する。
- [ ] バックエンドとフロントエンドのテスト、coverage、lint、format check、型チェック、production buildが成功する。
- [ ] コードレビューで CRITICAL・HIGH の未解決指摘がない。
