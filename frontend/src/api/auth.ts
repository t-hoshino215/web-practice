/** 認証関連のAPI呼び出し。 */

import { request, requestVoid } from './client';
import { loginResponseSchema, userSchema, type User } from './schemas';

export function registerUser(username: string, password: string): Promise<User> {
  return request('/users', userSchema, { method: 'POST', body: { username, password } });
}

export async function login(username: string, password: string): Promise<User> {
  const result = await request('/login', loginResponseSchema, {
    method: 'POST',
    body: { username, password },
  });

  return result.user;
}

export async function logout(): Promise<void> {
  await requestVoid('/logout', { method: 'POST', csrf: true });
}

export function fetchCurrentUser(): Promise<User> {
  return request('/users/me', userSchema);
}

export function refreshCsrf(): Promise<void> {
  return requestVoid('/auth/csrf', { method: 'POST' });
}
