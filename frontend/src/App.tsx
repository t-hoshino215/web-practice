/**
 * 画面全体の組み立てと、非同期処理の共通エラーハンドリング。
 */

import { useCallback, useEffect, useState } from 'react';

import { isUnauthorized, toMessage } from './api/errors';
import { AuthPanel } from './components/AuthPanel';
import { Header } from './components/Header';
import { MessageForm } from './components/MessageForm';
import { MessageList } from './components/MessageList';
import { Notice, type NoticeState } from './components/Notice';
import { useAuth } from './hooks/useAuth';
import { useMessages } from './hooks/useMessages';

export function App() {
  const { status, user, bootstrapNotice, login, register, logout, expire } = useAuth();
  const { messages, reload, add, archive, clear } = useMessages();

  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [busy, setBusy] = useState(false);

  /**
   * 非同期処理の共通ラッパー。
   * 二重送信の防止・通知のリセット・例外の画面向け変換をここに集約する。
   * 戻り値は成功可否。フォーム側が入力をクリアするかの判断に使う。
   */
  const runAction = useCallback(
    async (action: () => Promise<void>): Promise<boolean> => {
      setNotice(null);
      setBusy(true);

      try {
        await action();

        return true;
      } catch (error: unknown) {
        if (isUnauthorized(error)) {
          expire();
          clear();
          setNotice({
            message: 'セッションが切れました。ログインし直してください。',
            kind: 'error',
          });

          return false;
        }

        setNotice({ message: toMessage(error), kind: 'error' });

        return false;
      } finally {
        setBusy(false);
      }
    },
    [expire, clear],
  );

  // ログイン直後と、再読み込み後のセッション復元後の両方でここを通る
  useEffect(() => {
    if (status !== 'authenticated') {
      return;
    }

    void runAction(reload);
  }, [status, reload, runAction]);

  const handleLogin = useCallback(
    (username: string, password: string): Promise<boolean> =>
      runAction(() => login(username, password)),
    [login, runAction],
  );

  const handleRegister = useCallback(
    (username: string, password: string): Promise<boolean> =>
      runAction(async () => {
        await register(username, password);
        await login(username, password);

        setNotice({ message: 'ユーザーを登録しました。', kind: 'success' });
      }),
    [register, login, runAction],
  );

  const handleLogout = useCallback((): void => {
    void runAction(async () => {
      await logout();
      clear();
    });
  }, [logout, clear, runAction]);

  const handleCreateMessage = useCallback(
    (text: string): Promise<boolean> => runAction(() => add(text)),
    [add, runAction],
  );

  const handleArchive = useCallback(
    (messageId: number): void => {
      void runAction(() => archive(messageId));
    },
    [archive, runAction],
  );

  // 起動時の復元メッセージは、以降の操作で出る通知に上書きされてよい
  const activeNotice =
    notice ??
    (bootstrapNotice === null ? null : { message: bootstrapNotice, kind: 'error' as const });

  return (
    <>
      <Header username={user?.username ?? null} disabled={busy} onLogout={handleLogout} />

      <main className="main">
        <Notice notice={activeNotice} />

        {status === 'loading' && <p className="loading">読み込み中…</p>}

        {status === 'anonymous' && (
          <section className="panel">
            <h2 className="panel__title">ログイン / ユーザー登録</h2>
            <AuthPanel disabled={busy} onLogin={handleLogin} onRegister={handleRegister} />
          </section>
        )}

        {status === 'authenticated' && (
          <section className="panel">
            <h2 className="panel__title">メッセージ</h2>
            <MessageForm disabled={busy} onSubmit={handleCreateMessage} />
            <MessageList messages={messages} disabled={busy} onArchive={handleArchive} />
          </section>
        )}
      </main>
    </>
  );
}
