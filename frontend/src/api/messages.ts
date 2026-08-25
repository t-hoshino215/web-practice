/** メッセージ関連のAPI呼び出し。 */

import { request } from './client';
import { messageListSchema, messageSchema, type Message } from './schemas';

export function fetchMessages(): Promise<Message[]> {
  return request('/messages', messageListSchema);
}

export function createMessage(text: string): Promise<Message> {
  return request('/messages', messageSchema, { method: 'POST', body: { text }, csrf: true });
}

export function archiveMessage(messageId: number): Promise<Message> {
  return request(`/messages/${messageId}/archive`, messageSchema, { method: 'PATCH', csrf: true });
}
