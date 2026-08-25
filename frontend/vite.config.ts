/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,
    // 開発サーバーへの /api リクエストをCaddy(80番)へ転送し、本番と同じ同一オリジン構成を再現する。
    // これによりCORS設定もCookieのSameSite変更も不要なまま開発できる。
    // changeOriginでHostヘッダーをtargetのホスト名へ書き換えないと、
    // Caddyには localhost:5173 が渡り、サイトブロックにマッチしない。
    proxy: {
      '/api': {
        target: 'http://localhost',
        changeOrigin: true,
      },
    },
  },

  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/main.tsx'],
    },
  },
});
