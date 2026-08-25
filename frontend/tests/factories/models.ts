/**
 * テストデータのfactory。
 * 連番を持たせているのは、idの衝突を気にせず複数件を組み立てられるようにするため。
 */

import type { Message, User } from '../../src/api/schemas';

const FIXED_TIMESTAMP = '2026-01-01T00:00:00Z';

let userSequence = 0;
let messageSequence = 0;

export function buildUser(overrides: Partial<User> = {}): User {
  userSequence += 1;

  return {
    id: userSequence,
    username: `user${userSequence}`,
    role: 'user',
    created_at: FIXED_TIMESTAMP,
    ...overrides,
  };
}

export function buildMessage(overrides: Partial<Message> = {}): Message {
  messageSequence += 1;

  return {
    id: messageSequence,
    text: `message ${messageSequence}`,
    is_archived: false,
    created_at: FIXED_TIMESTAMP,
    ...overrides,
  };
}
