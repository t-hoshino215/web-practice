/**
 * メッセージ一覧の取得と更新を提供するフック。
 *
 * 作成・アーカイブの後は一覧を取り直す。楽観的更新に比べてリクエストは増えるが、
 * サーバー側の状態と画面が必ず一致するため、STEP 9 と同じ方針を踏襲する。
 */

import { useCallback, useState } from 'react';

import * as messagesApi from '../api/messages';
import type { Message } from '../api/schemas';

export interface UseMessagesResult {
  readonly messages: readonly Message[];
  readonly reload: () => Promise<void>;
  readonly add: (text: string) => Promise<void>;
  readonly archive: (messageId: number) => Promise<void>;
  readonly clear: () => void;
}

export function useMessages(): UseMessagesResult {
  const [messages, setMessages] = useState<readonly Message[]>([]);

  const reload = useCallback(async (): Promise<void> => {
    setMessages(await messagesApi.fetchMessages());
  }, []);

  const add = useCallback(
    async (text: string): Promise<void> => {
      await messagesApi.createMessage(text);
      await reload();
    },
    [reload],
  );

  const archive = useCallback(
    async (messageId: number): Promise<void> => {
      await messagesApi.archiveMessage(messageId);
      await reload();
    },
    [reload],
  );

  const clear = useCallback((): void => {
    setMessages([]);
  }, []);

  return { messages, reload, add, archive, clear };
}
