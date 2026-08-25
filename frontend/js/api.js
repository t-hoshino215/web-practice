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
// 現在のバックエンドは、ログイン時にCSRFトークンを返すので、フロントエンドはそれをsessionStorageに保持する。

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
