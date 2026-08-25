/**
 * 例外を、画面に表示できるメッセージへ変換する。
 * APIエラー・スキーマ不一致・ネットワーク断を区別して扱う。
 */

import { ZodError } from 'zod';

import { ApiError } from './client';

export function toMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }

  // backendのレスポンス形式が変わった場合。フロント側のバグとして切り分けられるようにする
  if (error instanceof ZodError) {
    return 'サーバーの応答形式が想定と異なります。時間をおいて再度お試しください。';
  }

  // fetch自体が失敗した場合（ネットワーク断など）
  return 'サーバーに接続できませんでした。通信環境を確認してください。';
}

/** セッション切れ（401）かどうか。呼び出し側でログイン画面へ戻す判断に使う。 */
export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}
