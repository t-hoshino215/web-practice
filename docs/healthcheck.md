# Health check command list

## ① localhost 向け

まずURLを変数にしておくと楽です。

```bash
BASE_URL="http://localhost"
COOKIE_FILE="/tmp/web-practice-cookies.txt"
SESSION_COOKIE_FILE="/tmp/web-practice-session-cookie.txt"
```

### [local] 基本ヘルスチェック

```bash
# FastAPI / Caddy の疎通確認
curl -i "$BASE_URL/api/health"

# PostgreSQL接続確認
curl -i "$BASE_URL/api/db-health"
```

どちらも基本的に、

```text
HTTP/1.1 200 OK
```

ならOKです。

### [local] テストユーザー登録

既存ユーザーと重ならない名前にします。

```bash
curl -i \
  "$BASE_URL/api/users" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "healthcheckuser",
    "password": "PracticePass123!"
  }'
```

期待値：

```text
201 Created
```

同じコマンドをもう一度実行して、

```text
409 Conflict
```

になることも確認します。

### [local] 間違ったパスワードでログイン

```bash
curl -i \
  "$BASE_URL/api/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "healthcheckuser",
    "password": "wrong-password"
  }'
```

期待値：

```text
401 Unauthorized
```

### [local] 正しいパスワードでログイン

まず古いCookieファイルを消します。

```bash
rm -f "$COOKIE_FILE"
```

ログインしてCookieを保存します。

```bash
curl -i \
  -c "$COOKIE_FILE" \
  "$BASE_URL/api/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "healthcheckuser",
    "password": "PracticePass123!"
  }'
```

期待値：

```text
200 OK
Set-Cookie: session=...
Set-Cookie: csrf_token=...; Path=/; Max-Age=...; SameSite=lax

{"user":..., "csrf_token":"..."}
```

Cookie確認：

```bash
cat "$COOKIE_FILE"
```

### CSRF Cookieからトークンを記録

```bash
CSRF_TOKEN=$(awk '$6 == "csrf_token" { print $7 }' "$COOKIE_FILE" | tail -n 1)
echo "CSRF_TOKEN=$CSRF_TOKEN"
```

JSONの `csrf_token` は既存クライアントとの互換性のため残っているが、ブラウザと同じ確認にするためCookieを正本として使います。

### [local] Cookieなし `/users/me`

```bash
curl -i "$BASE_URL/api/users/me"
```

期待値：

```text
401 Unauthorized
```

### [local] Cookieあり `/users/me`

```bash
curl -i -b "$COOKIE_FILE" "$BASE_URL/api/users/me"
```

期待値：

```text
200 OK
```

レスポンスに、

```json
{
  "username": "healthcheckuser"
}
```

などが含まれれば認証成功です 🔐

### [local] ログアウト (CSRFトークンなし)

```bash
curl -i -b "$COOKIE_FILE" -X POST "$BASE_URL/api/logout"
```

期待値：

```text
403 Forbidden
...

{"detail":"CSRF token required"}
```

### [local] ログアウト (無効なCSRFトークン)

```bash
curl -i -b "$COOKIE_FILE" -H "X-CSRF-Token: invalid-token" -X POST "$BASE_URL/api/logout"
```

期待値：

```text
403 Forbidden
...

{"detail":"Invalid CSRF token"}
```

Cookieには正しい値が入っていても、ヘッダーが異なれば拒否されます。

### [local] CSRF Cookieの再発行

Session Cookieだけを残したCookie jarを作ります。

```bash
awk '$6 != "csrf_token"' "$COOKIE_FILE" > "$SESSION_COOKIE_FILE"
```

CSRF Cookieなしでも、認証済みSessionがあれば再発行できます。

```bash
curl -i \
  -b "$SESSION_COOKIE_FILE" \
  -c "$COOKIE_FILE" \
  -X POST \
  "$BASE_URL/api/auth/csrf"
```

期待値：

```text
204 No Content
Set-Cookie: csrf_token=...
```

新しいCookie値をヘッダー用変数へ反映します。

```bash
CSRF_TOKEN=$(awk '$6 == "csrf_token" { print $7 }' "$COOKIE_FILE" | tail -n 1)
```

### [local] ログアウト (CSRFトークンあり)

```bash
curl -i -b "$COOKIE_FILE" -c "$COOKIE_FILE" -H "X-CSRF-Token: $CSRF_TOKEN" -X POST "$BASE_URL/api/logout"
```

期待値：

```text
204 No Content
Set-Cookie: session=...; Max-Age=0; Path=/
Set-Cookie: csrf_token=...; Max-Age=0; Path=/
```

ログアウト後：

```bash
curl -i -b "$COOKIE_FILE" "$BASE_URL/api/users/me"
```

期待値：

```text
401 Unauthorized
```

---

## ② 公開サーバー向け

公開ドメインを設定します。

```bash
BASE_URL="https://api.example.com"
COOKIE_FILE="/tmp/web-practice-public-cookies.txt"
```

`api.example.com` は実際のドメインに置き換えてください。

### [public] 基本ヘルスチェック

```bash
curl -i "$BASE_URL/api/health"

curl -i "$BASE_URL/api/db-health"
```

両方、

```text
200 OK
```

なら、

```text
Internet
 ↓ HTTPS
Caddy
 ↓
FastAPI
 ↓
PostgreSQL
```

まで正常です。

### [public] ユーザー登録

```bash
curl -i \
  "$BASE_URL/api/users" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "publichealthcheck",
    "password": "PracticePass123!"
  }'
```

期待値：

```text
201 Created
```

もう一度実行：

```text
409 Conflict
```

### [public] 正常ログイン

```bash
rm -f "$COOKIE_FILE"

curl -i \
  -c "$COOKIE_FILE" \
  "$BASE_URL/api/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "publichealthcheck",
    "password": "PracticePass123!"
  }'
```

期待値：

```text
200 OK
```

公開環境ではさらに `Set-Cookie` に、

```text
Secure
SameSite=Lax
```

が両Cookieに付いていること、`HttpOnly` はSession Cookieだけに付いていることも確認するとGOODです。

例えばレスポンスヘッダーに、

```text
Set-Cookie: session=...; Path=/; Max-Age=...; Secure; HttpOnly; SameSite=lax
Set-Cookie: csrf_token=...; Path=/; Max-Age=...; Secure; SameSite=lax
```

のように出ていればOKです。

### [public] Cookie認証

```bash
curl -i -b "$COOKIE_FILE" "$BASE_URL/api/users/me"
```

期待値：

```text
200 OK
```

CSRF Cookieの値をヘッダー用変数へ読み込みます。

```bash
CSRF_TOKEN=$(awk '$6 == "csrf_token" { print $7 }' "$COOKIE_FILE" | tail -n 1)
```

### [public] ログアウト

```bash
curl -i -b "$COOKIE_FILE" -c "$COOKIE_FILE" -H "X-CSRF-Token: $CSRF_TOKEN" -X POST "$BASE_URL/api/logout"
```

期待値：

```text
204 No Content
```

さらに、

```bash
curl -i -b "$COOKIE_FILE" "$BASE_URL/api/users/me"
```

で、

```text
401 Unauthorized
```

ならSession削除まで正常です。

---

## DB側も確認するなら

localhost環境：

```bash
docker compose exec db sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT id, username, created_at FROM users ORDER BY id;"'
```

Session：

```bash
docker compose exec db sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT id, user_id, token_hash, expires_at FROM auth_sessions ORDER BY id;"'
```

ログイン中ならSessionが存在し、ログアウト後に該当Sessionが消えていれば完璧です。

## 最低限これだけ通れば全体OK

```text
GET  /api/health          → 200
GET  /api/db-health       → 200

POST /api/users           → 201
同じユーザー再登録     → 409

POST /api/login
  間違ったpassword    → 401
  正しいpassword      → 200 + Session/CSRF Cookie

GET  /api/users/me
  Cookieなし          → 401
  Cookieあり          → 200

POST /api/auth/csrf       → 204 + 新しいCSRF Cookie
POST /api/logout
  CSRFヘッダーなし    → 403
  3者一致             → 204 + 両Cookie削除

GET  /api/users/me
  ログアウト後        → 401
```

これが **localhost / 公開サーバーの両方で通れば、STEP 8までの主要経路はかなりしっかり動作確認できています** 🎉

ちなみにWindowsの `curl.exe` で公開サーバーだけ以前のSchannel失効確認エラーが出る場合は、公開URLのコマンドに `--ssl-revoke-best-effort` を足せばOKです。
