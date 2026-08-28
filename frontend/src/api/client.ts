/**
 * FastAPIバックエンドとの通信の土台。
 *
 * 前提:
 * - フロントエンドとAPIは同一オリジンで配信されるため、CORSの考慮は不要
 * - Session CookieはHttpOnlyでJSからは読めないが、同一オリジンなので自動送信される
 * - 状態変更リクエストはX-CSRF-Tokenヘッダーを要求する（backend側のrequire_csrf）
 */

import type { ZodType } from 'zod';

const API_BASE = '/api';
const CSRF_COOKIE_NAME = 'csrf_token';

/**
 * APIがエラーを返したときに投げる例外。
 * 呼び出し側がHTTPステータスで分岐できるようにstatusを保持する。
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// --- CSRFトークンの取得 ---
// Cookieはタブや同一ホストのポート間で共有されるため、状態変更の直前に現在値を読む。

export function getCsrfToken(): string | null {
  const csrfCookie = document.cookie
    .split(';')
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(`${CSRF_COOKIE_NAME}=`));

  if (csrfCookie === undefined) {
    return null;
  }

  const encodedToken = csrfCookie.slice(CSRF_COOKIE_NAME.length + 1);

  try {
    const token = decodeURIComponent(encodedToken);

    return token.length > 0 ? token : null;
  } catch {
    return null;
  }
}

// --- エラーレスポンスの整形 ---

/** 未知の値から detail プロパティを安全に取り出す。 */
function extractDetail(payload: unknown): unknown {
  if (typeof payload !== 'object' || payload === null || !('detail' in payload)) {
    return undefined;
  }

  return payload.detail;
}

interface ValidationErrorItem {
  readonly loc?: unknown;
  readonly msg: string;
}

function isValidationErrorItem(item: unknown): item is ValidationErrorItem {
  return typeof item === 'object' && item !== null && 'msg' in item && typeof item.msg === 'string';
}

/**
 * FastAPIのエラーレスポンスを、画面に出せる1行の文字列へ変換する。
 * HTTPExceptionはdetailが文字列、Pydanticの検証エラー(422)はdetailが配列になるため両方扱う。
 */
function formatDetail(payload: unknown, status: number): string {
  const detail = extractDetail(payload);

  if (typeof detail === 'string') {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail.filter(isValidationErrorItem).map((item) => {
      const field = Array.isArray(item.loc) ? item.loc.at(-1) : null;

      return typeof field === 'string' ? `${field}: ${item.msg}` : item.msg;
    });

    if (messages.length > 0) {
      return messages.join(' / ');
    }
  }

  return `リクエストに失敗しました (HTTP ${status})`;
}

// --- リクエスト ---

export interface RequestOptions {
  readonly method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  readonly body?: unknown;
  readonly csrf?: boolean;
}

/** 実際の送信とHTTPレベルのエラー処理。スキーマ検証の手前まで行う。 */
async function send(path: string, options: RequestOptions): Promise<unknown> {
  const { method = 'GET', body, csrf = false } = options;

  const headers: Record<string, string> = {};

  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  if (csrf) {
    const token = getCsrfToken();

    // トークンが無いまま送っても403になるので、リクエスト前に落として理由を明示する
    if (token === null) {
      throw new ApiError(403, 'CSRFトークンがありません。ログインし直してください。');
    }

    headers['X-CSRF-Token'] = token;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    // 同一オリジンなので既定でもCookieは送られるが、意図を明示しておく
    credentials: 'same-origin',
    body: body === undefined ? null : JSON.stringify(body),
  });

  // 204 No Content（ログアウト）はボディが無い
  if (response.status === 204) {
    return undefined;
  }

  // プロキシ設定ミスなどでHTMLが返る場合もあるため、JSON解析の失敗は握って後段で扱う
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(response.status, formatDetail(payload, response.status));
  }

  return payload;
}

/**
 * ボディを持つエンドポイント用。レスポンスをZodスキーマで検証してから返す。
 * スキーマに合わない場合はZodErrorが投げられる（errors.ts で画面向けに変換する）。
 */
export async function request<T>(
  path: string,
  schema: ZodType<T>,
  options: RequestOptions = {},
): Promise<T> {
  return schema.parse(await send(path, options));
}

/** 204 No Content を返すエンドポイント用。 */
export async function requestVoid(path: string, options: RequestOptions = {}): Promise<void> {
  await send(path, options);
}
