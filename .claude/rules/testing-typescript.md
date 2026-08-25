---
paths:
  - "src/**/*.test.ts"
  - "tests/**/*.test.ts"
---

# TypeScript testing

## フレームワーク

TypeScriptスクリプトのテストフレームワークは `Vitest` を使用する

## カバレッジ

```bash
pnpm vitest run --coverage
```

## 命名規則

- テストファイル格納先: ソースファイルと同階層（コロケーション）に配置する。統合テスト・E2Eテストは `tests/` 配下
- テストファイル名: <英子文字ケバブケース> + .test.ts
  例: `src/features/auth/login.service.test.ts`
- `describe` ブロック名（外側）: テスト対象のクラス名または関数名をそのまま記載
  例: `describe('LoginService', () => { ... })`
- `describe` ブロック名（内側）: テスト対象のメソッド名または機能名を記載
  例: `describe('login', () => { ... })`
- テスト関数名（`it` / `test`）: should + <何をテストするかを英語で記載> + when + <条件>
  例: `it('should return a token when credentials are valid', ...)`

## 記載ルール

- AAAパターンでテストを書くこと（Arrange, Act, Assert）
- 原則として1つのテスト関数で1つのアサーションを書くこと
- `vitest` の `describe.concurrent` や `it.skip` / `it.only` などのタグでテストのカテゴリ・実行制御を行う
- 共通フィクスチャは `beforeEach` / `afterEach` または Vitest の `fixtures` で定義する。スコープを適切に設定すること
- 外部APIのモックは `vi.mock` / `vi.spyOn` を使う
- テストデータは `tests/factories/` の factory パターン（`factory-bot` などのライブラリも可）で作成する
- 同系統のケースは `it.each` でまとめること

Example:

```ts
import { describe, it, expect } from 'vitest';

describe('LoginService', () => {
  describe('login', () => {
    it('should return a token when credentials are valid', () => {
      // Arrange: define variables
      const username = 'testuser';
      const password = 'password123';

      // Act
      const result = loginService.login(username, password);

      // Assert
      expect(result).toHaveProperty('token');
    });

    it.each([
      ['invalid username', 'wrongpassword'],
      ['valid username', 'wrongpassword'],
    ])('should throw an error when credentials are invalid: %s', (username, password) => {
      // Act & Assert
      expect(() => loginService.login(username, password)).toThrowError();
    });
  });
});
```