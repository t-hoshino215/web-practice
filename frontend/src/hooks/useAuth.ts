/**
 * 認証状態を保持し、ログイン／登録／ログアウトとセッション復元を提供するフック。
 */

import { useCallback, useEffect, useState } from 'react';

import * as authApi from '../api/auth';
import { getCsrfToken } from '../api/client';
import { isUnauthorized, toMessage } from '../api/errors';
import type { User } from '../api/schemas';

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

export interface UseAuthResult {
  readonly status: AuthStatus;
  readonly user: User | null;
  /** 起動時のセッション復元で表示すべきメッセージ。無ければnull */
  readonly bootstrapNotice: string | null;
  readonly login: (username: string, password: string) => Promise<void>;
  readonly register: (username: string, password: string) => Promise<void>;
  readonly logout: () => Promise<void>;
  /** セッション切れを検知したときにログイン画面へ戻す */
  readonly expire: () => void;
}

export function useAuth(): UseAuthResult {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<User | null>(null);
  const [bootstrapNotice, setBootstrapNotice] = useState<string | null>(null);

  // 再読み込み時のセッション復元。
  // Session CookieはHttpOnlyでJSからは読めないため、/api/users/me を叩いて判定する。
  useEffect(() => {
    let cancelled = false;

    async function restore(): Promise<void> {
      try {
        const current = await authApi.fetchCurrentUser();

        if (cancelled) {
          return;
        }

        // 認証セッションが有効でもCSRF Cookieだけ欠落している場合は、
        // 現在のセッションに紐づく値を再発行してから認証済み状態へ進む。
        if (getCsrfToken() === null) {
          await authApi.refreshCsrf();
        }

        if (cancelled) {
          return;
        }

        setUser(current);
        setStatus('authenticated');
      } catch (error: unknown) {
        if (cancelled) {
          return;
        }

        setStatus('anonymous');

        // 未ログイン(401)は正常な状態なのでエラー表示しない
        if (!isUnauthorized(error)) {
          setBootstrapNotice(toMessage(error));
        }
      }
    }

    void restore();

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string): Promise<void> => {
    const authenticated = await authApi.login(username, password);

    setUser(authenticated);
    setStatus('authenticated');
    setBootstrapNotice(null);
  }, []);

  const register = useCallback(async (username: string, password: string): Promise<void> => {
    // 登録APIはログイン状態にしないため、呼び出し側で続けてloginする
    await authApi.registerUser(username, password);
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    await authApi.logout();

    setUser(null);
    setStatus('anonymous');
  }, []);

  const expire = useCallback((): void => {
    setUser(null);
    setStatus('anonymous');
  }, []);

  return { status, user, bootstrapNotice, login, register, logout, expire };
}
