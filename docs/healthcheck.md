# Health check command list

## ① localhost 向け

まずURLを変数にしておくと楽です。

```bash
BASE_URL="http://localhost"
COOKIE_FILE="/tmp/web-practice-cookies.txt"
```

### [local] 基本ヘルスチェック

```bash
# FastAPI / Caddy の疎通確認
curl -i "$BASE_URL/health"

# PostgreSQL接続確認
curl -i "$BASE_URL/db-health"
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
  "$BASE_URL/users" \
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
  "$BASE_URL/login" \
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
  "$BASE_URL/login" \
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
```

Cookie確認：

```bash
cat "$COOKIE_FILE"
```

### [local] Cookieなし `/users/me`

```bash
curl -i "$BASE_URL/users/me"
```

期待値：

```text
401 Unauthorized
```

### [local] Cookieあり `/users/me`

```bash
curl -i -b "$COOKIE_FILE" "$BASE_URL/users/me"
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

### [local] ログアウト

```bash
curl -i -b "$COOKIE_FILE" -c "$COOKIE_FILE" -X POST "$BASE_URL/logout"
```

期待値：

```text
204 No Content
```

ログアウト後：

```bash
curl -i -b "$COOKIE_FILE" "$BASE_URL/users/me"
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
curl -i "$BASE_URL/health"

curl -i "$BASE_URL/db-health"
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
  "$BASE_URL/users" \
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
  "$BASE_URL/login" \
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
HttpOnly
SameSite=Lax
```

が付いていることも確認するとGOODです。

例えばレスポンスヘッダーに、

```text
Set-Cookie: session=...; Path=/; Max-Age=...; Secure; HttpOnly; SameSite=lax
```

のように出ていればOKです。

### [public] Cookie認証

```bash
curl -i -b "$COOKIE_FILE" "$BASE_URL/users/me"
```

期待値：

```text
200 OK
```

### [public] ログアウト

```bash
curl -i -b "$COOKIE_FILE" -c "$COOKIE_FILE" -X POST "$BASE_URL/logout"
```

期待値：

```text
204 No Content
```

さらに、

```bash
curl -i -b "$COOKIE_FILE" "$BASE_URL/users/me"
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
GET  /health          → 200
GET  /db-health       → 200

POST /users           → 201
同じユーザー再登録     → 409

POST /login
  間違ったpassword    → 401
  正しいpassword      → 200 + Cookie

GET  /users/me
  Cookieなし          → 401
  Cookieあり          → 200

POST /logout          → 204

GET  /users/me
  ログアウト後        → 401
```

これが **localhost / 公開サーバーの両方で通れば、STEP 8までの主要経路はかなりしっかり動作確認できています** 🎉

ちなみにWindowsの `curl.exe` で公開サーバーだけ以前のSchannel失効確認エラーが出る場合は、公開URLのコマンドに `--ssl-revoke-best-effort` を足せばOKです。
