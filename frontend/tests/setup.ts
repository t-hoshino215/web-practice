/**
 * Vitestの共通セットアップ。
 * vite.config.ts の test.setupFiles から、全テストファイルの前に読み込まれる。
 */

// toBeInTheDocument などのDOM向けマッチャをexpectへ登録する
import '@testing-library/jest-dom/vitest';

import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(() => {
  // レンダリング結果を破棄する。残しておくとgetByRoleが前のテストの要素を拾う
  cleanup();

  // CSRFトークンの保存先。テスト間で状態を持ち越さない
  sessionStorage.clear();
});
