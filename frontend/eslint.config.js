import eslint from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    // Flat Configでは「ignoresだけのオブジェクト」が全体への除外指定になる
    ignores: ['**/dist/**', '**/node_modules/**', '**/coverage/**', '**/*.config.js', '**/.tmp/**'],
  },
  {
    // ブラウザ実行前提のコード。document / fetch などを既知のグローバルとして扱う
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      // Hooksの呼び出し規則と依存配列の不足を検出する。Reactでは実質必須
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/consistent-type-imports': 'warn',
    },
  },
  {
    // Node環境で動く設定ファイル
    files: ['vite.config.ts'],
    languageOptions: {
      globals: globals.node,
    },
  },
);
