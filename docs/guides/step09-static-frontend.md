# STEP 9: 静的フロントエンド導入手順書

HTML / CSS / JavaScript の静的ファイルでフロントエンドを構築し、Caddy から配信して公開するまでの手順書。

## このガイドのゴール

ブラウザからアクセスして、**ユーザー登録・ログイン・メッセージの作成・一覧・アーカイブ・ログアウト**が一通り操作できる画面を、既存の公開サーバー上で動かす。

### 完成後の構成

```text
ブラウザ
  ↓ HTTPS (443)
Caddy ─┬─ /api/*  → FastAPI (backend:8000) → PostgreSQL
       └─ /*      → 静的ファイル (/srv/frontend)
```

フロントエンドとAPIを**同一オリジン**で配信するのがこの構成の要点。これにより次の2つが自動的に解決する。

- **CORS設定が不要** — ブラウザのクロスオリジン制限に一切かからない
- **Cookieがそのまま動く** — 既存の `SameSite=Lax` のSession Cookieを変更せずに使える

### 前提

- STEP 8 までが完了しており、`make up` でAPIが起動すること
- `curl -i http://localhost/health` が `200 OK` を返すこと
- 公開手順（STEP 9-8）を実施する場合は、OCI VM と Cloudflare のドメインが設定済みであること

### 全体の流れ

| # | 手順 | 変更対象 |
| --- | --- | --- |
| 9-1 | APIに `/api` プレフィックスを付ける | `backend/` |
| 9-2 | フロントエンドの雛形を作る | `frontend/` |
| 9-3 | Caddyから静的ファイルを配信する | `Caddyfile`, `compose.yaml` |
| 9-4 | CSSでスタイルを整える | `frontend/css/` |
| 9-5 | APIクライアントを実装する | `frontend/js/api.js` |
| 9-6 | 画面描画を実装する | `frontend/js/ui.js` |
| 9-7 | 画面の初期化とイベント配線を実装する | `frontend/js/main.js` |
| 9-8 | 公開する | OCI / Cloudflare |
| 9-9 | 動作確認 | - |

---

## 9-1. APIに `/api` プレフィックスを付ける

### なぜ必要か

現在のAPIは `/health` や `/login` のようにルート直下にある。このままだと、ルート直下から配信したい静的ファイル（`/index.html`, `/css/style.css` など）とパスが混在し、Caddy側でAPIのパスを1つずつ列挙して振り分ける必要が出てくる。

APIを `/api` 配下にまとめておけば、Caddyの振り分けは `/api/*` の1行で済み、今後APIを追加してもCaddyfileを触らずに済む。

### 変更前後

| 変更前 | 変更後 |
| --- | --- |
| `GET /` | `GET /api/` |
| `GET /health` | `GET /api/health` |
| `GET /db-health` | `GET /api/db-health` |
| `POST /users` | `POST /api/users` |
| `GET /users/me` | `GET /api/users/me` |
| `POST /login` | `POST /api/login` |
| `POST /logout` | `POST /api/logout` |
| `GET` `POST` `/messages` | `/api/messages` |
| `PATCH /messages/{id}/archive` | `PATCH /api/messages/{id}/archive` |
| `GET /admin/users` `GET /admin/messages` | `/api/admin/...` |
| `GET /docs` | `GET /api/docs` |

### 手順 1: テストを先に更新する（Red）

プロジェクトの方針はTDDなので、まず期待値を書き換えてテストが落ちることを確認する。

`backend/tests/test_main.py` の期待ルート集合を `/api` 付きに変更する。

```python
    assert {
        ("GET", "/api/"),
        ("GET", "/api/health"),
        ("GET", "/api/db-health"),
        ("GET", "/api/messages"),
        ("POST", "/api/messages"),
        ("PATCH", "/api/messages/{message_id}/archive"),
        ("POST", "/api/users"),
        ("GET", "/api/users/me"),
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/messages"),
        ("POST", "/api/login"),
        ("POST", "/api/logout"),
    } <= routes
```

`backend/` で実行して落ちることを確認する。

```bash
uv run pytest tests/test_main.py
```

### 手順 2: `main.py` を変更する（Green）

`backend/src/web_practice/main.py` の `create_app()` を次のように書き換える。

```python
from fastapi import APIRouter, FastAPI


def create_app() -> FastAPI:
    """FastAPIアプリケーションを生成し、各ルーターを /api 配下に登録する。"""
    # 静的フロントエンドと同一オリジンで配信するため、APIドキュメントも /api 配下へ寄せる。
    app = FastAPI(
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # ルート直下は静的ファイルの配信に使うため、APIは全て /api プレフィックスの下にまとめる。
    api_router = APIRouter(prefix="/api")

    api_router.include_router(health_router)
    api_router.include_router(messages_router)
    api_router.include_router(users_router)
    api_router.include_router(admin_router)
    api_router.include_router(auth_router)

    app.include_router(api_router)

    return app
```

変更点は3つ。

1. `from fastapi import FastAPI` を `from fastapi import APIRouter, FastAPI` にする
2. `prefix="/api"` を持つ `APIRouter` を親として、各ルーターをその下にまとめる
3. `docs_url` / `redoc_url` / `openapi_url` を `/api` 配下へ移す

> **3番目を忘れないこと。** `docs_url` などはアプリ全体の設定で、`APIRouter` のプレフィックスの影響を受けない。指定しないと Swagger UI は `/docs` のまま残り、Caddyが `/api/*` しかbackendへ転送しないため **404になってSwagger UIが開けなくなる**。

### 手順 3: 残りのテストのURLを更新する

`backend/tests/` にURLリテラルが多数ある。まとめて置換する。

```bash
cd backend/tests

grep -rlE '"/(health|db-health|login|logout|users|messages|admin)' . \
  | xargs sed -i -E 's#"/(health|db-health|login|logout|users|messages|admin)#"/api/\1#g'
```

**この置換では拾えない箇所が2つある**ので手で直す。ルートパス `"/"` は上の正規表現に一致しないため。

`backend/tests/routers/test_health.py`:

```python
@pytest.mark.parametrize(
    ("path", "expected"),
    [("/api/", {"message": "Hello, Web Server!"}), ("/api/health", {"status": "ok"})],
)
```

`backend/tests/test_main.py` の `("GET", "/")` は手順1で `("GET", "/api/")` に直してある。まだなら直す。

### 手順 4: テストを通す

```bash
cd backend
uv run pytest
```

> **注意: `tests/test_config.py` の13件は、この変更を行う前から失敗している。**
> `CONFIG_PATH = Path(__file__).parents[1] / "web_practice" / "config.py"` が srcレイアウト移行後のパスに追従できておらず、`FileNotFoundError` になる。
> `/api` への移行とは無関係なので、切り分けの際に混同しないこと。先に直す場合は次のようにする。
>
> ```python
> CONFIG_PATH = Path(__file__).parents[1] / "src" / "web_practice" / "config.py"
> ```
>
> この1行を直せば **132 passed / 1 skipped**、直さずに除外した場合は **119 passed / 1 skipped** になる。
>
> ```bash
> uv run pytest --ignore=tests/test_config.py
> ```

置換漏れがないか、URLリテラルを一覧して確認しておくとよい。

```bash
grep -rhoE '"/[a-z/{}._-]*"' tests/ | sort -u
```

`"/api/..."` だけが並んでいればよい。

### 手順 5: ドキュメントを更新する

`docs/healthcheck.md` に書かれた確認用URLも `/api` 付きに置き換える。**2種類の書き方が混在している**ので、2回置換する。

```bash
# 1. curlコマンド内の $BASE_URL/... （18箇所）
sed -i -E 's#\$BASE_URL/(health|db-health|login|logout|users|messages|admin)#$BASE_URL/api/\1#g' docs/healthcheck.md

# 2. 末尾「最低限これだけ通れば全体OK」のサマリ内のパス（7箇所）
sed -i -E 's#^(GET|POST|PATCH|DELETE)( +)/(health|db-health|login|logout|users|messages|admin)#\1\2/api/\3#' docs/healthcheck.md
```

置換漏れがないことを確認する。

```bash
grep -nE '(\$BASE_URL|^(GET|POST|PATCH|DELETE) +)/(health|db-health|login|logout|users|messages|admin)' docs/healthcheck.md
```

何も出力されなければ完了。

### 手順 6: 起動して確認する

```bash
docker compose --env-file ./backend/.env build backend
docker compose --env-file ./backend/.env up -d backend

curl -i http://localhost/api/health      # → 200 OK
curl -i http://localhost/health          # → 404 Not Found（移行できている証拠）
```

ブラウザで `http://localhost/api/docs` を開き、Swagger UI が表示されることも確認する。

---

## 9-2. フロントエンドの雛形を作る

### ディレクトリ構成

`frontend/` に次の構成を作る。役割ごとにファイルを分け、1ファイルが大きくなりすぎないようにする。

```text
frontend/
├── index.html          # 画面の構造
├── css/
│   └── style.css       # 見た目
└── js/
    ├── api.js          # API通信・CSRF・エラー整形
    ├── ui.js           # DOM描画（XSS対策の中心）
    └── main.js         # 初期化とイベント配線
```

```bash
mkdir -p frontend/css frontend/js
```

### `frontend/index.html`

```html
<!DOCTYPE html>
<html lang="ja">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Web Practice</title>
    <link rel="stylesheet" href="/css/style.css" />
    <!-- type="module" のスクリプトは自動で defer されるため、DOM構築後に実行される -->
    <script type="module" src="/js/main.js"></script>
  </head>
  <body>
    <header class="header">
      <h1 class="header__title">Web Practice</h1>
      <div class="header__user" id="header-user" hidden>
        <span id="current-username"></span>
        <button type="button" id="logout-button">ログアウト</button>
      </div>
    </header>

    <main class="main">
      <p class="notice" id="notice" hidden></p>

      <section class="panel" id="auth-panel" hidden>
        <h2 class="panel__title">ログイン / ユーザー登録</h2>
        <form class="form" id="auth-form">
          <label class="form__label" for="username">ユーザー名</label>
          <input
            class="form__input"
            id="username"
            name="username"
            type="text"
            required
            minlength="3"
            maxlength="50"
            pattern="[A-Za-z0-9_-]+"
            autocomplete="username"
          />

          <label class="form__label" for="password">パスワード</label>
          <input
            class="form__input"
            id="password"
            name="password"
            type="password"
            required
            minlength="8"
            maxlength="128"
            autocomplete="current-password"
          />

          <div class="form__actions">
            <button class="button button--primary" type="submit">ログイン</button>
            <button class="button" type="button" id="register-button">新規登録</button>
          </div>
        </form>
      </section>

      <section class="panel" id="messages-panel" hidden>
        <h2 class="panel__title">メッセージ</h2>
        <form class="form form--inline" id="message-form">
          <input
            class="form__input"
            id="message-text"
            name="text"
            type="text"
            required
            maxlength="255"
            placeholder="メッセージを入力"
          />
          <button class="button button--primary" type="submit">追加</button>
        </form>

        <ul class="message-list" id="message-list"></ul>
        <p class="message-list__empty" id="message-empty" hidden>メッセージはまだありません。</p>
      </section>
    </main>
  </body>
</html>
```

> `minlength` / `maxlength` / `pattern` は、バックエンドの Pydantic スキーマ（`UserCreate`, `MessageCreate`）の制約に合わせてある。
> ただし **HTML側の検証はUXのためのものであり、セキュリティ境界ではない**。ブラウザの検証は簡単に迂回できるため、サーバー側の検証が本体である。

---

## 9-3. Caddyから静的ファイルを配信する

### `Caddyfile`

```caddyfile
# 既存のAPI専用ドメイン（curlでの動作確認やAPIクライアント向けに残す）
api.taph-lab.com {
    reverse_proxy backend:8000
}

# フロントエンド + API（同一オリジン）
taph-lab.com {
    encode gzip zstd

    handle /api/* {
        reverse_proxy backend:8000
    }

    handle {
        root * /srv/frontend
        try_files {path} /index.html
        file_server
    }
}

# ローカル確認用
http://localhost {
    encode gzip zstd

    handle /api/* {
        reverse_proxy backend:8000
    }

    handle {
        root * /srv/frontend
        try_files {path} /index.html
        file_server
    }
}
```

押さえておくべき点。

- **`handle` であって `handle_path` ではない。** `handle_path` はマッチしたプレフィックスを**削って**転送するため、`/api/health` が `/health` として backend に届いてしまい404になる。`handle` はパスをそのまま渡す。
- **`handle` ブロックは相互排他で、書いた順に評価される。** `/api/*` を先に書き、静的配信のブロックを後に書く。
- **`try_files {path} /index.html`** は、実ファイルが無いパスへのアクセスで `index.html` を返す設定。今は1ページなので必須ではないが、STEP 10 で React のクライアントサイドルーティングを導入するときに必要になるので今のうちに入れておく。副作用として、存在しないパスが404ではなく200 + `index.html` を返すようになる（トラブルシューティング参照）。

### `compose.yaml`

`caddy` サービスに `frontend/` を読み取り専用でマウントする。

```yaml
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./frontend:/srv/frontend:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - backend
    restart: unless-stopped
```

`:ro`（read-only）にしておくことで、Webサーバーからホスト側のファイルが書き換えられないようにする。

### 反映と確認

```bash
docker compose up -d caddy

# 設定ファイルの文法チェック（設定ミスの切り分けに便利）
docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile

curl -i http://localhost/           # → 200, Content-Type: text/html
curl -i http://localhost/api/health # → 200, {"status":"ok"}
```

`validate` の出力が `Valid configuration` で終わればよい。

> `Caddyfile input is not formatted` という警告が出ることがあるが、これはインデントがタブでないというだけの指摘で動作には影響しない。既存の `Caddyfile` も4スペースで書かれているため、スタイルを揃えたままで問題ない。

ブラウザで `http://localhost/` を開き、フォームが表示されればここまで完了。

> Caddyfile だけを変更した場合は、再起動せずに設定を再読み込みできる。
>
> ```bash
> docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
> ```

---

## 9-4. CSSでスタイルを整える

### `frontend/css/style.css`

```css
:root {
  --color-bg: #f5f6f8;
  --color-surface: #ffffff;
  --color-text: #1f2933;
  --color-muted: #6b7280;
  --color-border: #d8dce3;
  --color-primary: #2563eb;
  --color-error: #b91c1c;
  --color-success: #15803d;
  --radius: 8px;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: system-ui, "Hiragino Sans", "Noto Sans JP", sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
  line-height: 1.6;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.5rem;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.header__title {
  margin: 0;
  font-size: 1.25rem;
}

.header__user {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.main {
  max-width: 720px;
  margin: 0 auto;
  padding: 1.5rem;
}

.panel {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1.25rem;
}

.panel__title {
  margin-top: 0;
  font-size: 1.05rem;
}

.form {
  display: grid;
  gap: 0.5rem;
}

.form--inline {
  grid-template-columns: 1fr auto;
  align-items: center;
  margin-bottom: 1rem;
}

.form__label {
  font-size: 0.875rem;
  color: var(--color-muted);
}

.form__input {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 1rem;
}

.form__input:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}

.form__actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.button {
  padding: 0.5rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-surface);
  font-size: 0.9375rem;
  cursor: pointer;
}

.button:hover:not(:disabled) {
  border-color: var(--color-primary);
}

.button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.button--primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #ffffff;
}

.notice {
  margin: 0 0 1rem;
  padding: 0.75rem 1rem;
  border-radius: var(--radius);
  border: 1px solid var(--color-error);
  color: var(--color-error);
  background: #fef2f2;
}

.notice[data-kind="success"] {
  border-color: var(--color-success);
  color: var(--color-success);
  background: #f0fdf4;
}

.message-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.5rem;
}

.message {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.message--archived {
  opacity: 0.55;
}

.message--archived .message__text {
  text-decoration: line-through;
}

.message__text {
  overflow-wrap: anywhere;
}

.message__time {
  font-size: 0.8125rem;
  color: var(--color-muted);
  white-space: nowrap;
}

.message-list__empty {
  color: var(--color-muted);
}
```

---

## 9-5. APIクライアントを実装する

ここが最も重要な部分。認証まわりで押さえるべき仕様が3つある。

1. **Session Cookieは `HttpOnly`** なのでJavaScriptからは読めない。読む必要もなく、同一オリジンなら `fetch` が自動で送る
2. **CSRFトークンはログインのレスポンスボディで返る**（Cookieではない）。状態変更リクエストでは `X-CSRF-Token` ヘッダーに載せる必要がある
3. **エラーレスポンスの `detail` は2種類ある** — `HTTPException` は文字列、Pydanticの検証エラー（422）は配列。両方扱えるようにする

### `frontend/js/api.js`

```javascript
/**
 * FastAPIバックエンドとの通信をまとめたモジュール。
 *
 * 前提:
 * - フロントエンドとAPIは同一オリジンで配信されるため、CORSの考慮は不要
 * - Session CookieはHttpOnlyでJSからは読めないが、同一オリジンなので自動送信される
 * - 状態変更リクエストはX-CSRF-Tokenヘッダーを要求する（backend側のrequire_csrf）
 */

const API_BASE = "/api";
const CSRF_STORAGE_KEY = "csrfToken";

/**
 * APIがエラーを返したときに投げる例外。
 * 呼び出し側がHTTPステータスで分岐できるようにstatusを保持する。
 */
export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// --- CSRFトークンの保持 ---
// sessionStorageを使う理由と制約はガイド本文の「既知の制約」を参照。

export function getCsrfToken() {
  return sessionStorage.getItem(CSRF_STORAGE_KEY);
}

function storeCsrfToken(token) {
  sessionStorage.setItem(CSRF_STORAGE_KEY, token);
}

export function clearCsrfToken() {
  sessionStorage.removeItem(CSRF_STORAGE_KEY);
}

/**
 * FastAPIのエラーレスポンスを、画面に出せる1行の文字列へ変換する。
 * HTTPExceptionはdetailが文字列、Pydanticの検証エラー(422)はdetailが配列になるため両方扱う。
 */
function formatDetail(payload, status) {
  const detail = payload?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = Array.isArray(item.loc) ? item.loc.at(-1) : null;
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .join(" / ");
  }

  return `リクエストに失敗しました (HTTP ${status})`;
}

/**
 * 共通のfetchラッパー。
 * @param {string} path - /api からの相対パス
 * @param {{method?: string, body?: object|null, csrf?: boolean}} options
 */
async function request(path, { method = "GET", body = null, csrf = false } = {}) {
  const headers = {};

  if (body !== null) {
    headers["Content-Type"] = "application/json";
  }

  if (csrf) {
    const token = getCsrfToken();

    // トークンが無いまま送っても403になるので、リクエスト前に落として理由を明示する
    if (token === null) {
      throw new ApiError(403, "CSRFトークンがありません。ログインし直してください。");
    }

    headers["X-CSRF-Token"] = token;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    // 同一オリジンなので既定でもCookieは送られるが、意図を明示しておく
    credentials: "same-origin",
    body: body === null ? null : JSON.stringify(body),
  });

  // 204 No Content（ログアウト）はボディが無い
  if (response.status === 204) {
    return null;
  }

  // プロキシ設定ミスなどでHTMLが返る場合もあるため、JSON解析の失敗は握って後段で扱う
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(response.status, formatDetail(payload, response.status));
  }

  return payload;
}

// --- 認証 ---

export function registerUser(username, password) {
  return request("/users", { method: "POST", body: { username, password } });
}

export async function login(username, password) {
  const result = await request("/login", {
    method: "POST",
    body: { username, password },
  });

  storeCsrfToken(result.csrf_token);

  return result.user;
}

export async function logout() {
  await request("/logout", { method: "POST", csrf: true });

  clearCsrfToken();
}

export function fetchCurrentUser() {
  return request("/users/me");
}

// --- メッセージ ---

export function fetchMessages() {
  return request("/messages");
}

export function createMessage(text) {
  return request("/messages", { method: "POST", body: { text }, csrf: true });
}

export function archiveMessage(messageId) {
  return request(`/messages/${messageId}/archive`, { method: "PATCH", csrf: true });
}
```

---

## 9-6. 画面描画を実装する

### `frontend/js/ui.js`

```javascript
/**
 * DOM操作をまとめたモジュール。
 *
 * XSS対策の方針: ユーザー由来の文字列は必ず textContent で挿入し、innerHTML は使わない。
 * innerHTML を使うと、メッセージ本文に <script> や onerror 属性を仕込まれた場合に実行されてしまう。
 */

const elements = {
  notice: document.getElementById("notice"),
  headerUser: document.getElementById("header-user"),
  currentUsername: document.getElementById("current-username"),
  authPanel: document.getElementById("auth-panel"),
  messagesPanel: document.getElementById("messages-panel"),
  messageList: document.getElementById("message-list"),
  messageEmpty: document.getElementById("message-empty"),
};

// --- 通知 ---

export function showNotice(message, kind = "error") {
  elements.notice.textContent = message;
  elements.notice.dataset.kind = kind;
  elements.notice.hidden = false;
}

export function clearNotice() {
  elements.notice.textContent = "";
  elements.notice.hidden = true;
}

// --- 画面の切り替え ---

export function showLoggedIn(user) {
  elements.currentUsername.textContent = user.username;
  elements.headerUser.hidden = false;
  elements.authPanel.hidden = true;
  elements.messagesPanel.hidden = false;
}

export function showLoggedOut() {
  elements.currentUsername.textContent = "";
  elements.headerUser.hidden = true;
  elements.authPanel.hidden = false;
  elements.messagesPanel.hidden = true;
  elements.messageList.replaceChildren();
  elements.messageEmpty.hidden = true;
}

// --- メッセージ一覧 ---

/**
 * メッセージ一覧を描画する。
 * 受け取った配列は変更せず、DOM要素へ変換するだけに留める。
 */
export function renderMessages(messages, { onArchive }) {
  const items = messages.map((message) => buildMessageItem(message, onArchive));

  elements.messageList.replaceChildren(...items);
  elements.messageEmpty.hidden = messages.length > 0;
}

function buildMessageItem(message, onArchive) {
  const item = document.createElement("li");
  item.className = message.is_archived ? "message message--archived" : "message";

  const text = document.createElement("span");
  text.className = "message__text";
  // APIから返る文字列は必ずtextContentで挿入する
  text.textContent = message.text;

  const time = document.createElement("time");
  time.className = "message__time";
  time.dateTime = message.created_at;
  time.textContent = new Date(message.created_at).toLocaleString("ja-JP");

  item.append(text, time);

  // アーカイブ済みには再度アーカイブするボタンを出さない
  if (!message.is_archived) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button";
    button.textContent = "アーカイブ";
    button.addEventListener("click", () => onArchive(message.id));

    item.append(button);
  }

  return item;
}
```

---

## 9-7. 画面の初期化とイベント配線を実装する

### `frontend/js/main.js`

```javascript
/**
 * 画面の初期化とイベント配線を行うエントリポイント。
 */

import * as api from "./api.js";
import * as ui from "./ui.js";

const authForm = document.getElementById("auth-form");
const registerButton = document.getElementById("register-button");
const logoutButton = document.getElementById("logout-button");
const messageForm = document.getElementById("message-form");
const messageText = document.getElementById("message-text");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");

/**
 * 例外を画面向けのメッセージへ変換する共通ハンドラ。
 * 401（セッション切れ）のときはログイン画面へ戻す。
 */
function handleError(error) {
  if (error instanceof api.ApiError && error.status === 401) {
    api.clearCsrfToken();
    ui.showLoggedOut();
    ui.showNotice("セッションが切れました。ログインし直してください。");
    return;
  }

  if (error instanceof api.ApiError) {
    ui.showNotice(error.message);
    return;
  }

  // ネットワーク断など、fetch自体が失敗した場合
  ui.showNotice("サーバーに接続できませんでした。通信環境を確認してください。");
}

/** 二重送信を防ぐため、非同期処理の間はフォームを無効化する。 */
async function withDisabled(form, action) {
  const fieldsets = Array.from(form.elements);
  fieldsets.forEach((element) => {
    element.disabled = true;
  });

  try {
    await action();
  } finally {
    fieldsets.forEach((element) => {
      element.disabled = false;
    });
  }
}

async function refreshMessages() {
  const messages = await api.fetchMessages();

  ui.renderMessages(messages, { onArchive: handleArchive });
}

async function handleArchive(messageId) {
  ui.clearNotice();

  try {
    await api.archiveMessage(messageId);
    await refreshMessages();
  } catch (error) {
    handleError(error);
  }
}

async function enterLoggedInState(user) {
  ui.showLoggedIn(user);
  await refreshMessages();
}

// --- イベント配線 ---

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  ui.clearNotice();

  await withDisabled(authForm, async () => {
    try {
      const user = await api.login(usernameInput.value, passwordInput.value);

      passwordInput.value = "";

      await enterLoggedInState(user);
    } catch (error) {
      handleError(error);
    }
  });
});

registerButton.addEventListener("click", async () => {
  ui.clearNotice();

  // HTMLの検証属性（minlength等）はsubmit以外では自動実行されないため明示的に呼ぶ
  if (!authForm.reportValidity()) {
    return;
  }

  await withDisabled(authForm, async () => {
    try {
      // 登録APIはログイン状態にしないため、続けてログインする
      await api.registerUser(usernameInput.value, passwordInput.value);

      const user = await api.login(usernameInput.value, passwordInput.value);

      passwordInput.value = "";

      ui.showNotice("ユーザーを登録しました。", "success");

      await enterLoggedInState(user);
    } catch (error) {
      handleError(error);
    }
  });
});

logoutButton.addEventListener("click", async () => {
  ui.clearNotice();

  try {
    await api.logout();
    ui.showLoggedOut();
  } catch (error) {
    handleError(error);
  }
});

messageForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  ui.clearNotice();

  await withDisabled(messageForm, async () => {
    try {
      await api.createMessage(messageText.value);

      messageText.value = "";

      await refreshMessages();
    } catch (error) {
      handleError(error);
    }
  });
});

// --- 起動時のセッション復元 ---

/**
 * 再読み込み時に、Cookieが有効ならログイン状態を復元する。
 *
 * Session CookieはHttpOnlyでJSからは読めないため、/api/users/me を叩いて判定する。
 * CookieはブラウザにあるがCSRFトークンがsessionStorageに無い場合（別タブで開いた等）は、
 * 状態変更APIが必ず403になるためログイン画面へ戻す。
 */
async function bootstrap() {
  try {
    const user = await api.fetchCurrentUser();

    if (api.getCsrfToken() === null) {
      ui.showLoggedOut();
      ui.showNotice("操作を続けるにはログインし直してください。");
      return;
    }

    await enterLoggedInState(user);
  } catch (error) {
    if (error instanceof api.ApiError && error.status === 401) {
      // 未ログインは正常な状態なのでエラー表示しない
      api.clearCsrfToken();
      ui.showLoggedOut();
      return;
    }

    ui.showLoggedOut();
    handleError(error);
  }
}

bootstrap();
```

---

## 9-8. 公開する

### 手順 1: DNSレコードを追加する

Cloudflare のDNS設定で、フロントエンド用のホスト名をOCI VMのパブリックIPへ向ける。

| Type | Name | Content | Proxy status |
| --- | --- | --- | --- |
| A | `@`（または `app`） | OCI VMのパブリックIP | `api` サブドメインと同じ設定に揃える |

> **Proxy status（オレンジ/グレーの雲）は既存の `api` サブドメインと同じにする。** Caddyの自動HTTPSはLet's Encryptのチャレンジ（HTTP-01 / TLS-ALPN-01）を通す必要があり、Cloudflareのプロキシを有効にすると経路が変わる。`api.taph-lab.com` が動いている設定をそのまま踏襲するのが確実。

`Caddyfile` に書いたホスト名（`taph-lab.com`）とDNSレコードを一致させること。

### 手順 2: サーバーへ反映する

OCI VM上で次を実行する。

```bash
git pull

# /api への移行が入っているのでbackendを再ビルドする
docker compose --env-file ./backend/.env build backend

docker compose --env-file ./backend/.env up -d backend
```

`frontend/` はバインドマウントなので、静的ファイルの更新だけならCaddyの再起動も再ビルドも不要（ブラウザのキャッシュのみ注意）。

### 手順 3: Cookieを本番設定にする

公開環境はHTTPSなので、`backend/.env` で `COOKIE_SECURE` を有効にする。

```bash
COOKIE_SECURE=true
```

```bash
docker compose up -d backend
```

これで Set-Cookie に `Secure` が付く。

### 手順 4: 証明書の取得を確認する

```bash
docker compose logs caddy | grep -i "certificate obtained"

curl -I https://taph-lab.com/
```

---

## 9-9. 動作確認

### ブラウザでの確認

`https://taph-lab.com/`（ローカルなら `http://localhost/`）を開いて次を順に確認する。

| # | 操作 | 期待する結果 |
| --- | --- | --- |
| 1 | 初期表示 | ログインフォームが表示される |
| 2 | 3文字未満のユーザー名で「新規登録」 | ブラウザの検証メッセージが出て送信されない |
| 3 | 有効な情報で「新規登録」 | 登録成功メッセージ → メッセージ画面へ遷移 |
| 4 | 同じユーザー名でもう一度「新規登録」 | `Username already exists` が表示される |
| 5 | メッセージを入力して「追加」 | 一覧に追加され、入力欄がクリアされる |
| 6 | 「アーカイブ」 | 取り消し線が付き、ボタンが消える |
| 7 | ページを再読み込み（F5） | ログイン状態と一覧が復元される |
| 8 | 「ログアウト」 | ログインフォームに戻る |
| 9 | ログアウト後に再読み込み | ログインフォームのまま（エラーは出ない） |
| 10 | 誤ったパスワードでログイン | `Invalid username or password` が表示される |

### DevToolsでの確認

#### Network タブ

- `POST /api/login` のレスポンスヘッダーに `Set-Cookie: session=...; HttpOnly; SameSite=lax` があること
- 公開環境ではさらに `Secure` が付いていること
- `POST /api/messages` のリクエストヘッダーに `X-CSRF-Token` があること
- `GET /`, `/css/style.css`, `/js/*.js` が `200` で返ること

#### Application タブ

- Cookies に `session` があり、`HttpOnly` にチェックが入っていること
- Session Storage に `csrfToken` があること

#### Console タブ

- エラーが出ていないこと

### XSS対策の確認

メッセージ本文に次を入力して追加する。

```text
<img src=x onerror=alert(1)>
```

**アラートが出ず、入力した文字列がそのまま表示されれば正しい。** `textContent` で挿入しているため、HTMLとして解釈されない。

### curlでの確認

`docs/healthcheck.md` の手順を `/api` 付きのURLで実行する。

```bash
BASE_URL="http://localhost"

curl -i "$BASE_URL/api/health"
curl -i "$BASE_URL/"            # 静的ファイルが返る
```

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| `/api/health` が404 | Caddyで `handle_path` を使っている | `handle` に変える（`handle_path` はプレフィックスを削る） |
| `/api/docs` が404 | `docs_url` を `/api/docs` にしていない | 9-1 手順2の3つ目の変更を行う |
| どのURLを開いてもindex.htmlが返る | `try_files` の副作用。JSやCSSのパスが間違っている | Networkタブで実際のレスポンスを確認し、パス（`/js/main.js` 等）を修正 |
| JSの変更が反映されない | ブラウザキャッシュ | ハードリロード（`Ctrl+Shift+R`）またはDevToolsの「Disable cache」 |
| Consoleに `Failed to load module script` | MIMEタイプ不正、またはファイルが見つからない | `curl -I http://localhost/js/main.js` で `Content-Type: text/javascript` と200を確認 |
| メッセージ追加で403 `CSRF token required` | sessionStorageにトークンが無い | 一度ログアウトしてログインし直す（後述の「既知の制約」） |
| メッセージ追加で403 `Invalid CSRF token` | 古いトークンが残っている | ログインし直す。DBのSessionを消した場合も同様 |
| 一覧取得で401 | Cookie未送信、または期限切れ | Applicationタブで `session` Cookieの有無と有効期限を確認 |
| 公開環境でログインできない | `COOKIE_SECURE` の設定不整合 | HTTPSなら `true`、HTTPなら `false` |
| 証明書が発行されない | DNS未反映、443番未開放、Cloudflareのプロキシ設定 | `dig taph-lab.com`、OCIのSecurity List、`docker compose logs caddy` を確認 |

---

## 既知の制約

### CSRFトークンとタブの関係

現在のバックエンドは、**ログイン時にしかCSRFトークンを発行しない**。フロントエンドはこれを `sessionStorage` に保持している。

`sessionStorage` はタブ単位なので、次のズレが起きる。

```text
同じタブで再読み込み(F5)
  → Cookie ○  sessionStorage ○  → 正常に復元される

新しいタブで同じURLを開く
  → Cookie ○  sessionStorage ✗  → ログイン済みだが状態変更ができない
```

このガイドの `bootstrap()` は後者を検出して「ログインし直してください」と表示する。**発生しても壊れないが、体験としては良くない。**

`localStorage` に変えればタブ間で共有されるが、ログアウト後も残る、複数アカウントを扱えないといった別の問題が出る。

**恒久対応**は、バックエンドに「現在のSessionのCSRFトークンを再発行する」エンドポイント（例: `GET /api/auth/csrf`）を追加し、起動時に `/api/users/me` と併せて取得すること。STEP 10 でフロントエンドを再構築する際に、合わせて検討するとよい。

> なお、CSRFトークンを `sessionStorage` に置くこと自体は、この設計では致命的ではない。CSRF攻撃は「別サイトから勝手にリクエストを送らせる」攻撃であり、別オリジンのスクリプトは同一オリジンポリシーによって `sessionStorage` を読めないため、トークンを盗めない。読めるのは同一オリジンで実行されるスクリプト＝XSSが成立している場合だが、その時点で他の防御も破られている。

### HTMLの検証はセキュリティではない

`minlength` や `pattern` はUXのための機能で、DevToolsから簡単に外せる。実際の防御は Pydantic スキーマによるサーバー側の検証が担っている。

### 静的ファイル配信のため `file://` では動かない

`index.html` をファイルとして直接開いても動かない。ESモジュールと `fetch` の相対パス解決にHTTPオリジンが必要なため、必ず `http://localhost/` 経由で開くこと。

---

## STEP 10（React + Vite）への引き継ぎ

この構成は、次のステップへそのまま移行できるように作ってある。

| 項目 | STEP 9（現在） | STEP 10（React + Vite） |
| --- | --- | --- |
| 配信元 | `./frontend` をマウント | `./frontend/dist` をマウント |
| Caddyfile | 変更なし | 変更なし（`root` のパスのみ） |
| `/api` 振り分け | `handle /api/*` | 変更なし |
| ルーティング | 単一ページ | `try_files` によりSPAルーティングが機能する |
| APIクライアント | `js/api.js` | TypeScript化して流用可能 |
| CORS | 不要 | 不要（開発サーバーは Vite の proxy 設定で同一オリジンにする） |

移行時の主な作業は、`frontend/` をViteプロジェクト化し、`compose.yaml` のマウント先を `./frontend/dist` に変えることの2点になる。

---

## 導入記録

この手順書に沿った導入記録。

| # | 手順 | ステータス | コミット |
| --- | --- | --- | --- |
| 9-1 | APIに `/api` プレフィックスを付ける | 完了 | ff707b28a47ba607763d08f526aca325cba496ec |
| 9-1 (修正) | `backend/tests/test_config.py` のパス追従失敗の問題の修正 | 完了 | de3de63023f230b4e3b3e2709694fa6b9064b9fa |
| 9-2 | フロントエンドの雛形を作る | 完了 | 237ed8d4c7fd734314503445fae7d2aee544e8e2 |
| 9-3 | Caddyから静的ファイルを配信する | 完了 | c6bb2f4f1d993fba5d787b85939e6a5c2085b27f |
| 9-4 | CSSでスタイルを整える | 完了 | 2e9e765c1c36c2318fd585cfaad65145dc134974 |
| 9-5 | APIクライアントを実装する | 完了 | 33e62daf28cb72b5531520179269d42b44fa2397 |
| 9-6 | 画面描画を実装する | 完了 | 0b96f41c8aafb4b294aee3fa47559bab25b7803c |
| 9-7 | 画面の初期化とイベント配線を実装する | 完了 | 001677f8c5829071ae11344c04887f0a86ae7b39 |
| 9-8 | 公開する | 完了 | - |
| 9-9 | 動作確認 | 完了 | - |
