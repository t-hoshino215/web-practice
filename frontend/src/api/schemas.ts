/**
 * APIレスポンスのスキーマ定義。
 * backend/src/web_practice/schemas/ のPydanticモデルと1対1で対応させる。
 * 型はスキーマから導出し、二重管理にならないようにする。
 */

import { z } from 'zod';

export const userSchema = z.object({
  id: z.number().int(),
  username: z.string(),
  role: z.string(),
  // FastAPIはdatetimeをISO8601文字列としてシリアライズする
  created_at: z.string(),
});

export type User = z.infer<typeof userSchema>;

export const messageSchema = z.object({
  id: z.number().int(),
  text: z.string(),
  is_archived: z.boolean(),
  created_at: z.string(),
});

export type Message = z.infer<typeof messageSchema>;

export const messageListSchema = z.array(messageSchema);

export const loginResponseSchema = z.object({
  user: userSchema,
  csrf_token: z.string(),
});

export type LoginResponse = z.infer<typeof loginResponseSchema>;
