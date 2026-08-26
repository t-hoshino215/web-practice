# STEP 10: TypeScript + React + Vite 移行手順書

STEP 9 で作った素のHTML/CSS/JavaScriptのフロントエンドを、TypeScript + React + Vite で再構築し、ビルド成果物をCaddyから配信するまでの手順書。

## このガイドのゴール

STEP 9 と**同じ機能**（ユーザー登録・ログイン・メッセージの作成／一覧／アーカイブ・ログアウト）を、型安全・テスト可能・ビルド前提のモダンなフロントエンド構成で動かす。

機能を増やさないのがこのSTEPの要点。**同じ振る舞いを別の技術基盤で再現する**ことで、ツールチェーンそのものの学習に集中できる。

### 完成後の構成

```text
[本番／ローカル確認]
ブラウザ
  ↓ HTTPS (443) / HTTP (80)
Caddy ─┬─ /api/*  → FastAPI (backend:8000) → PostgreSQL
       └─ /*      → /srv/frontend （Viteのビルド成果物をイメージに同梱）

[開発時]
ブラウザ
  ↓ HTTP (5173)
Vite dev server ─┬─ /api/*  → proxy → Caddy(80) → FastAPI
                 └─ /*      → HMR付きのReactアプリ
```

同一オリジン配信という STEP 9 の方針は変えない。開発時も Vite の `server.proxy` で `/api` を同一オリジンに見せるため、**CORS設定は最後まで不要**であり、Cookieもそのまま動く。

### 前提

- STEP 9 までが完了しており、`make up` で `http://localhost/` にフォーム画面が出ること
- `curl -i http://localhost/api/health` が `200 OK` を返すこと
- Node.js 20 以上が使えること（開発コンテナには Node 24 が入っている）
- 公開手順（10-11）を実施する場合は、OCI VM と Cloudflare のドメインが設定済みであること

### 全体の流れ

| # | 手順 | 変更対象 |
| --- | --- | --- |
| 10-1 | ゴールと構成を確認する | - |
| 10-2 | Node と pnpm を用意する | `Dockerfile` |
| 10-3 | Viteプロジェクトの雛形を作る | `frontend/` |
| 10-4 | テスト環境を整える | `frontend/tests/` |
| 10-5 | APIクライアントを実装する | `frontend/src/api/` |
| 10-6 | 状態管理フックを実装する | `frontend/src/hooks/` |
| 10-7 | UIコンポーネントを実装する | `frontend/src/components/` |
| 10-8 | アプリを組み立てる | `frontend/src/App.tsx` ほか |
| 10-9 | 開発サーバーで動作確認する | - |
| 10-10 | ビルド成果物をCaddyから配信する | `frontend/Dockerfile`, `compose.yaml`, `Caddyfile` |
| 10-11 | 公開する | OCI / Cloudflare |
| 10-12 | 動作確認 | - |
| 10-13 | ドキュメントを更新する | `README.md`, `CLAUDE.md` |

---

## 10-1. ゴールと構成を確認する

### なぜ移行するのか

STEP 9 の構成には、規模が大きくなると効いてくる限界がある。

| STEP 9 の課題 | STEP 10 での解決 |
| --- | --- |
| APIレスポンスの形が保証されない。`message.txt` のような綴り間違いが実行時まで分からない | TypeScript と Zod で、コンパイル時と実行時の両方で検証する |
| `document.getElementById` による手続き的なDOM操作。状態と表示の同期を人間が保証している | Reactが状態から表示を導出する |
| テストが書けない。DOM前提のコードをNode上で実行できない | Vitest + jsdom + Testing Library でユニットテストを書く |
| ファイルを分けてもブラウザが1つずつ取りに行く。依存の解決が読み込み順序頼み | Viteがバンドル・minify・ハッシュ付きファイル名を生成する |
| 保存してリロードするまで結果が分からない | Vite の HMR で即座に反映される |

### 配信方法の選択

ビルドが必要になったことで、「`dist/` を誰がいつ作るか」を決める必要が出てくる。

| 方式 | 内容 | 判断 |
| --- | --- | --- |
| A. ホストでビルドして `./frontend/dist` をバインドマウント | STEP 9 の延長。設定変更は最小 | 公開サーバー（OCI VM）にもNodeとpnpmが必要になる |
| B. 多段Dockerビルドで `dist` をCaddyイメージに同梱 | `frontend/Dockerfile` の builder ステージでビルドし、`caddy:2-alpine` へ `COPY --from` | **採用**。サーバー側はDockerだけで完結し、STEP 11 のCI/CDにもそのまま乗る |

このガイドは **B** で進める。`backend/Dockerfile` が builder / runtime の多段構成になっているのと同じ考え方で、フロントエンドも「ビルド環境」と「配信環境」を分離する。

> ビルド成果物 `frontend/dist/` はコミットしない。ルートの `.gitignore` にすでに `dist/` があるため、そのままで除外される。

### 移行後のディレクトリ構成

```text
frontend/
├── index.html                  # Viteのエントリポイント（プロジェクト直下である必要がある）
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json               # アプリ（ブラウザ）用
├── tsconfig.node.json          # 設定ファイル（Node）用
├── vite.config.ts              # Vite・dev server proxy・Vitest
├── eslint.config.js
├── .prettierrc
├── .prettierignore
├── .gitignore
├── .dockerignore
├── Dockerfile                  # builder(node) → runtime(caddy)
├── src/
│   ├── main.tsx                # ReactのDOMマウント
│   ├── App.tsx                 # 画面全体の組み立てとエラーハンドリング
│   ├── styles/
│   │   └── global.css          # STEP 9 の style.css を流用
│   ├── api/
│   │   ├── schemas.ts          # Zodスキーマとそこから導出した型
│   │   ├── client.ts           # fetchラッパー・ApiError・CSRF保持
│   │   ├── client.test.ts
│   │   ├── errors.ts           # 例外 → 画面向けメッセージ
│   │   ├── errors.test.ts
│   │   ├── auth.ts             # register / login / logout / me
│   │   └── messages.ts         # list / create / archive
│   ├── hooks/
│   │   ├── useAuth.ts          # 認証状態とセッション復元
│   │   └── useMessages.ts      # メッセージ一覧の取得と更新
│   └── components/
│       ├── Notice.tsx
│       ├── Header.tsx
│       ├── AuthPanel.tsx
│       ├── MessageForm.tsx
│       ├── MessageItem.tsx
│       ├── MessageList.tsx
│       └── MessageList.test.tsx
└── tests/
    ├── setup.ts                # Vitestの共通セットアップ
    └── factories/
        └── models.ts           # テストデータのfactory
```

ユニットテストはソースと同階層（コロケーション）、共通のセットアップとfactoryは `tests/` 配下。`.claude/rules/typescript-testing.md` の規約に合わせている。

---

## 10-2. Node と pnpm を用意する

このプロジェクトのフロントエンドのパッケージマネージャーは pnpm。開発コンテナには Node は入っているが **pnpm は入っていない**ので用意する。

### ホストで用意する

Node 20+ に同梱されている Corepack を使うのが手軽。`package.json` の `packageManager` フィールドに書いたバージョンが自動で使われる。

```bash
node -v          # v20 以上であること
corepack enable pnpm
pnpm -v
```

> `EACCES` で失敗する場合は、Nodeがシステム領域にインストールされている。`sudo corepack enable pnpm` を使う。
> Corepackが使えない環境では `npm install -g pnpm@10` でも代替できる。

### 開発コンテナに常設する

`make up-dev` / `make exec-dev` で作業する場合は、イメージ側にも入れておく。ルートの `Dockerfile` の `dev` ステージを次のように変更する。

```dockerfile
    && curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g markdownlint-cli2 \
    && corepack enable pnpm

# Corepackが初回実行時に対話プロンプトを出さないようにする（非TTYの環境で固まるのを防ぐ）
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
```

反映する。

```bash
make up-dev
make exec-dev

# コンテナ内で確認
pnpm -v
```

---

## 10-3. Viteプロジェクトの雛形を作る

### 既存ファイルの扱い

Viteは**プロジェクト直下の `index.html`** をエントリポイントとして扱うため、STEP 9 の `frontend/index.html` は置き換えになる。CSSは中身をそのまま使えるので移動する。

```bash
cd frontend

# CSSは流用する。git mv で履歴を残す
mkdir -p src/styles
git mv css/style.css src/styles/global.css
rmdir css

# HTML/JS はReact版へ作り直すため削除する（内容はgit履歴とSTEP 9の手順書に残る）
git rm index.html js/api.js js/ui.js js/main.js
```

> **⚠ ここから 10-10 を完了するまで、`http://localhost/` は正しく表示されない。**
> `compose.yaml` は現在 `./frontend` をそのままCaddyへマウントしているため、この状態のまま公開サーバーへ反映すると `package.json` や `src/` の中身がそのまま配信されてしまう。
> **10-10 まで進めるまでは公開サーバーへ反映しないこと。** 開発中の確認は 10-9 の Vite 開発サーバー（`http://localhost:5173`）で行う。

### 依存関係をインストールする

`frontend/.tmp/` に置いた他プロジェクトの設定ファイルをベースにするが、**バージョンは手書きせず `pnpm add` に解決させる**。ロックファイル（`pnpm-lock.yaml`）が再現性を担保する。

```bash
cd frontend

pnpm init

# 実行時依存
pnpm add react react-dom zod

# ビルド・型
pnpm add -D vite @vitejs/plugin-react typescript @types/react @types/react-dom @types/node

# Lint / Format
pnpm add -D eslint @eslint/js typescript-eslint eslint-plugin-react-hooks eslint-plugin-react-refresh globals prettier

# テスト
pnpm add -D vitest @vitest/coverage-v8 jsdom @testing-library/react @testing-library/dom @testing-library/jest-dom @testing-library/user-event
```

`.tmp/package.json` からの主な変更点は次の3つ。

| 項目 | `.tmp` のまま | このプロジェクト | 理由 |
| --- | --- | --- | --- |
| `tsx` | devDependencyにある | **入れない** | Node単体で走らせるスクリプトが無い。Viteがすべて担う |
| `zod` | 無い | **追加** | `.claude/rules/code-style.md` の「境界ではスキーマベースの検証を行う」を守るため |
| バージョン指定 | `"latest"` | `pnpm add` が書いた範囲指定 | `latest` は解決結果が毎回変わり、ビルドが再現しない |

### package.json

`pnpm init` と `pnpm add` が生成した内容に、`name` / `type` / `packageManager` / `scripts` を手で書き足す。

```json
{
  "name": "web-practice-frontend",
  "version": "0.1.0",
  "description": "Web Practice のフロントエンド（TypeScript + React + Vite）",
  "private": true,
  "type": "module",
  "packageManager": "pnpm@10.33.4",
  "scripts": {
    "dev": "vite",
    "build": "pnpm typecheck && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "typecheck": "tsc -p tsconfig.json && tsc -p tsconfig.node.json",
    "lint": "eslint .",
    "lint:fix": "eslint . --fix",
    "format": "prettier --write .",
    "format:check": "prettier --check ."
  }
}
```

押さえるべき点。

- **`"type": "module"` は必須。** `.tmp/package.json` には無いが、これが無いと `eslint.config.js` と `vite.config.ts` の `import` 文が解釈できない。
- **`build` で先に型チェックする。** Viteはトランスパイルするだけで型エラーを検出しない。`vite build` 単体では型の壊れたコードがそのまま通ってしまう。
- `dev` は `.tmp` のプレースホルダから `vite` へ差し替える。

### tsconfig.json

`.tmp/tsconfig.json` をブラウザ + React + Vite 向けに調整する。

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "types": ["vite/client"],
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "noEmit": true,
    "noUncheckedIndexedAccess": false,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "verbatimModuleSyntax": true
  },
  "include": ["src", "tests"],
  "exclude": ["dist", "node_modules", "coverage"]
}
```

`.tmp` からの変更点と理由。

| 変更 | 理由 |
| --- | --- |
| `outDir` / `rootDir` / `sourceMap` を削除 | `noEmit: true` なので `tsc` は何も出力しない。バンドルとsourcemapはViteが行う |
| `moduleResolution: "bundler"` を追加 | 拡張子なしの `import './App'` をバンドラと同じ規則で解決する |
| `lib` に `DOM` / `DOM.Iterable` を追加 | `document` / `fetch` / `sessionStorage` などブラウザAPIの型が必要 |
| `types: ["vite/client"]` を追加 | `import.meta.env` とCSSインポートの型が入る。未指定だと `@types/node` まで巻き込まれ、ブラウザ用コードにNodeの型が混ざる |
| `jsx: "react-jsx"` を追加 | React 17以降の新しいJSX変換。`import React from 'react'` が不要になる |
| `verbatimModuleSyntax: true` を追加 | `.tmp/eslint.config.js` の `consistent-type-imports` ルールをコンパイラ側でも強制する。型だけのインポートは `import type` と書く必要がある |
| `include` に `tests` を追加 | `tests/factories/` をテストから参照するため |

> `noUncheckedIndexedAccess` は `.tmp` の設定どおり `false` のままにしてある。`true` にすると配列アクセスがすべて `T | undefined` になり厳密だが、既存テンプレートの方針を優先した。

### tsconfig.node.json

`vite.config.ts` は**ブラウザではなくNode上**で実行される設定ファイル。アプリ本体とは型環境が違うので分ける。

```json
{
  "compilerOptions": {
    "target": "ES2023",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2023"],
    "types": ["node"],
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "noEmit": true,
    "isolatedModules": true,
    "verbatimModuleSyntax": true
  },
  "include": ["vite.config.ts"]
}
```

分けない場合、アプリ側のコードから `process` や `fs` が「型としては存在する」ことになり、ブラウザで動かないコードを書いてもコンパイルが通ってしまう。

### vite.config.ts

```typescript
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
```

先頭の `/// <reference types="vitest/config" />` が無いと、`defineConfig` に `test` キーを渡した時点で型エラーになる。

### eslint.config.js

`.tmp/eslint.config.js` に、ブラウザのグローバルとReact向けルールを足す。

```javascript
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
    // ブラウザ実行前提のコード。document / fetch / sessionStorage を既知のグローバルとして扱う
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
```

> `eslint-plugin-react-hooks` は、バージョンによって提供するプリセット名（`configs.recommended` / `configs['recommended-latest']` / `configs.flat.recommended`）が変わってきた経緯がある。ここではルールを直接指定してバージョン差を避けている。プリセットを使う場合は導入したバージョンのREADMEを確認すること。

### .prettierrc と .prettierignore

`.tmp/.prettierrc` は**変更なしでそのまま使える**。

```bash
cp .tmp/.prettierrc .prettierrc
```

`.prettierignore` はリポジトリルート想定で書かれている（`.devcontainer/` や `.claude/` を参照している）ので、`frontend/` 配下向けに書き直す。

```text
# 依存とビルド成果物
node_modules/
dist/
coverage/

# Markdown はリポジトリ全体で markdownlint-cli2 が管理する
*.md

# CLI生成物（手で整形しない）
pnpm-lock.yaml

# 他プロジェクトから持ち込んだ設定の置き場
.tmp/
```

> Prettier 3 は既定で `.gitignore` も参照するが、参照するのは**実行ディレクトリ直下の `.gitignore`**。`frontend/` で `pnpm format` を実行する以上、リポジトリルートの `.gitignore` は効かない。`node_modules/` などを `.prettierignore` にも明記しておくのが確実。

### .gitignore と .dockerignore

`frontend/.gitignore` を新規作成する。ルートの `.gitignore` はPython向けで、**`node_modules/` の記述が無い**。

```text
node_modules/
dist/
coverage/
*.tsbuildinfo
.vite/
```

`frontend/.dockerignore` も作る。10-10 のイメージビルドでホストの `node_modules` を持ち込まないようにするため。

```text
node_modules
dist
coverage
.tmp
*.local
```

### index.html

Vite用に置き換える。CSSの `<link>` とスクリプトの直書きは不要になり、`src/main.tsx` が唯一の起点になる。

```html
<!doctype html>
<html lang="ja">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Web Practice</title>
  </head>
  <body>
    <div id="root"></div>
    <!-- ビルド時にハッシュ付きのバンドルへ差し替えられる。CSSも main.tsx 経由で取り込まれる -->
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

### 設定ファイルの確認

この時点では `src/main.tsx` がまだ無いので起動はしない。設定ファイルの構文だけ確認しておく。

```bash
pnpm lint
pnpm format:check
```

---

## 10-4. テスト環境を整える

実装より先にテストの土台を用意する。プロジェクトの方針はTDDなので、以降の各ステップは「テストを書く → 落ちることを確認 → 実装して通す」の順で進める。

### `frontend/tests/setup.ts`

```typescript
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
```

### `frontend/tests/factories/models.ts`

テストデータは直書きせずfactoryで作る。「このテストで意味を持つ値」だけを `overrides` で指定でき、テストの意図が読み取りやすくなる。

```typescript
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
```

### テストランナーの確認

```bash
pnpm test
```

この時点ではテストファイルが無いので `No test files found` になる。設定エラーで落ちなければ正しい。

---

## 10-5. APIクライアントを実装する

### 設計方針

STEP 9 の `js/api.js` をTypeScript化する。押さえるべき仕様はSTEP 9 と同じ3点。

1. Session Cookie は `HttpOnly` なのでJSから読めない。同一オリジンなら `fetch` が自動で送る
2. CSRFトークンはログインのレスポンスボディで返る。状態変更リクエストでは `X-CSRF-Token` ヘッダーに載せる
3. エラーレスポンスの `detail` は2種類ある（`HTTPException` は文字列、Pydanticの検証エラー(422)は配列）

TypeScript化にあたって1点追加する。**`fetch(...).json()` の戻り値は実行時まで形が分からない**ため、そこに型注釈を書いただけでは「宣言しただけ」で検証にはならない。境界で Zod により実際に検証し、型はスキーマから導出する。

```text
fetch → JSON.parse → Zod schema.parse → 型が保証された値
                        ↑ ここが型の境界
```

### `frontend/src/api/schemas.ts`

`backend/src/web_practice/schemas/` のPydanticモデルと1対1で対応させる。フィールド名はAPIが返すsnake_caseのまま扱い、変換層は作らない（マッピングを増やすほど、両者のズレに気付きにくくなる）。

```typescript
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
```

### テストを先に書く（Red）

`frontend/src/api/client.test.ts` を作る。この時点では `client.ts` が無いので実行すると失敗する。

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { buildMessage } from '../../tests/factories/models';
import { ApiError, request, storeCsrfToken } from './client';
import { messageSchema } from './schemas';

/**
 * fetchの戻り値を最小限で模したヘルパー。
 * jsdom環境ではResponseの実体があるとは限らないため、必要なプロパティだけを持つ値を使う。
 */
function stubResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

describe('client', () => {
  describe('request', () => {
    beforeEach(() => {
      vi.stubGlobal('fetch', vi.fn());
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it('should return the validated payload when the response matches the schema', async () => {
      // Arrange
      const message = buildMessage();
      vi.mocked(fetch).mockResolvedValue(stubResponse(message));

      // Act
      const result = await request('/messages/1', messageSchema);

      // Assert
      expect(result).toEqual(message);
    });

    it('should prefix the path with /api when calling fetch', async () => {
      // Arrange
      vi.mocked(fetch).mockResolvedValue(stubResponse(buildMessage()));

      // Act
      await request('/messages/1', messageSchema);

      // Assert
      expect(fetch).toHaveBeenCalledWith('/api/messages/1', expect.anything());
    });

    it('should send the X-CSRF-Token header when csrf is required', async () => {
      // Arrange
      storeCsrfToken('test-token');
      vi.mocked(fetch).mockResolvedValue(stubResponse(buildMessage()));

      // Act
      await request('/messages', messageSchema, { method: 'POST', body: { text: 'hi' }, csrf: true });

      // Assert
      expect(fetch).toHaveBeenCalledWith(
        '/api/messages',
        expect.objectContaining({
          headers: expect.objectContaining({ 'X-CSRF-Token': 'test-token' }),
        }),
      );
    });

    it('should throw ApiError before sending when csrf is required but no token is stored', async () => {
      // Act & Assert
      await expect(request('/messages', messageSchema, { method: 'POST', csrf: true })).rejects.toBeInstanceOf(
        ApiError,
      );
    });

    it('should throw ApiError carrying the status when the API returns an error', async () => {
      // Arrange
      vi.mocked(fetch).mockResolvedValue(stubResponse({ detail: 'Username already exists' }, 409));

      // Act & Assert
      await expect(request('/users', messageSchema, { method: 'POST' })).rejects.toMatchObject({
        status: 409,
        message: 'Username already exists',
      });
    });

    it('should join field names and messages when the API returns a 422 validation error', async () => {
      // Arrange
      const detail = [
        { loc: ['body', 'username'], msg: 'String should have at least 3 characters' },
        { loc: ['body', 'password'], msg: 'String should have at least 8 characters' },
      ];
      vi.mocked(fetch).mockResolvedValue(stubResponse({ detail }, 422));

      // Act & Assert
      await expect(request('/users', messageSchema, { method: 'POST' })).rejects.toThrowError(
        'username: String should have at least 3 characters / password: String should have at least 8 characters',
      );
    });

    it.each([
      ['HTMLが返った場合', null],
      ['detailが無い場合', {}],
    ])('should fall back to a generic message when the error body is unusable: %s', async (_label, body) => {
      // Arrange
      vi.mocked(fetch).mockResolvedValue(stubResponse(body, 500));

      // Act & Assert
      await expect(request('/messages', messageSchema)).rejects.toThrowError(
        'リクエストに失敗しました (HTTP 500)',
      );
    });
  });
});
```

```bash
pnpm test
```

`Failed to resolve import "./client"` で落ちればRed。

### `frontend/src/api/client.ts`（Green）

```typescript
/**
 * FastAPIバックエンドとの通信の土台。
 *
 * 前提:
 * - フロントエンドとAPIは同一オリジンで配信されるため、CORSの考慮は不要
 * - Session CookieはHttpOnlyでJSからは読めないが、同一オリジンなので自動送信される
 * - 状態変更リクエストはX-CSRF-Tokenヘッダーを要求する（backend側のrequire_csrf）
 */

import type { ZodType } from 'zod';

const API_BASE = '/api';
const CSRF_STORAGE_KEY = 'csrfToken';

/**
 * APIがエラーを返したときに投げる例外。
 * 呼び出し側がHTTPステータスで分岐できるようにstatusを保持する。
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// --- CSRFトークンの保持 ---
// 現在のバックエンドはログイン時にしかCSRFトークンを発行しないため、
// レスポンスで受け取った値をsessionStorageに保持する。制約は「既知の制約」を参照。

export function getCsrfToken(): string | null {
  return sessionStorage.getItem(CSRF_STORAGE_KEY);
}

export function storeCsrfToken(token: string): void {
  sessionStorage.setItem(CSRF_STORAGE_KEY, token);
}

export function clearCsrfToken(): void {
  sessionStorage.removeItem(CSRF_STORAGE_KEY);
}

// --- エラーレスポンスの整形 ---

/** 未知の値から detail プロパティを安全に取り出す。 */
function extractDetail(payload: unknown): unknown {
  if (typeof payload !== 'object' || payload === null || !('detail' in payload)) {
    return undefined;
  }

  return payload.detail;
}

interface ValidationErrorItem {
  readonly loc?: unknown;
  readonly msg: string;
}

function isValidationErrorItem(item: unknown): item is ValidationErrorItem {
  return typeof item === 'object' && item !== null && 'msg' in item && typeof item.msg === 'string';
}

/**
 * FastAPIのエラーレスポンスを、画面に出せる1行の文字列へ変換する。
 * HTTPExceptionはdetailが文字列、Pydanticの検証エラー(422)はdetailが配列になるため両方扱う。
 */
function formatDetail(payload: unknown, status: number): string {
  const detail = extractDetail(payload);

  if (typeof detail === 'string') {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail.filter(isValidationErrorItem).map((item) => {
      const field = Array.isArray(item.loc) ? item.loc.at(-1) : null;

      return typeof field === 'string' ? `${field}: ${item.msg}` : item.msg;
    });

    if (messages.length > 0) {
      return messages.join(' / ');
    }
  }

  return `リクエストに失敗しました (HTTP ${status})`;
}

// --- リクエスト ---

export interface RequestOptions {
  readonly method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  readonly body?: unknown;
  readonly csrf?: boolean;
}

/** 実際の送信とHTTPレベルのエラー処理。スキーマ検証の手前まで行う。 */
async function send(path: string, options: RequestOptions): Promise<unknown> {
  const { method = 'GET', body, csrf = false } = options;

  const headers: Record<string, string> = {};

  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  if (csrf) {
    const token = getCsrfToken();

    // トークンが無いまま送っても403になるので、リクエスト前に落として理由を明示する
    if (token === null) {
      throw new ApiError(403, 'CSRFトークンがありません。ログインし直してください。');
    }

    headers['X-CSRF-Token'] = token;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    // 同一オリジンなので既定でもCookieは送られるが、意図を明示しておく
    credentials: 'same-origin',
    body: body === undefined ? null : JSON.stringify(body),
  });

  // 204 No Content（ログアウト）はボディが無い
  if (response.status === 204) {
    return undefined;
  }

  // プロキシ設定ミスなどでHTMLが返る場合もあるため、JSON解析の失敗は握って後段で扱う
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(response.status, formatDetail(payload, response.status));
  }

  return payload;
}

/**
 * ボディを持つエンドポイント用。レスポンスをZodスキーマで検証してから返す。
 * スキーマに合わない場合はZodErrorが投げられる（errors.ts で画面向けに変換する）。
 */
export async function request<T>(
  path: string,
  schema: ZodType<T>,
  options: RequestOptions = {},
): Promise<T> {
  return schema.parse(await send(path, options));
}

/** 204 No Content を返すエンドポイント用。 */
export async function requestVoid(path: string, options: RequestOptions = {}): Promise<void> {
  await send(path, options);
}
```

```bash
pnpm test
```

Green になることを確認する。

### `frontend/src/api/errors.ts`

例外を画面向けのメッセージへ変換する処理を1か所へ集める。STEP 9 では `main.js` の `handleError()` にあった役割。

```typescript
/**
 * 例外を、画面に表示できるメッセージへ変換する。
 * APIエラー・スキーマ不一致・ネットワーク断を区別して扱う。
 */

import { ZodError } from 'zod';

import { ApiError } from './client';

export function toMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }

  // backendのレスポンス形式が変わった場合。フロント側のバグとして切り分けられるようにする
  if (error instanceof ZodError) {
    return 'サーバーの応答形式が想定と異なります。時間をおいて再度お試しください。';
  }

  // fetch自体が失敗した場合（ネットワーク断など）
  return 'サーバーに接続できませんでした。通信環境を確認してください。';
}

/** セッション切れ（401）かどうか。呼び出し側でログイン画面へ戻す判断に使う。 */
export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}
```

対応するテスト `frontend/src/api/errors.test.ts` も書いておく。

```typescript
import { describe, expect, it } from 'vitest';
import { ZodError } from 'zod';

import { ApiError } from './client';
import { isUnauthorized, toMessage } from './errors';

describe('errors', () => {
  describe('toMessage', () => {
    it('should return the API message when the error is an ApiError', () => {
      // Arrange
      const error = new ApiError(409, 'Username already exists');

      // Act & Assert
      expect(toMessage(error)).toBe('Username already exists');
    });

    it('should return the schema mismatch message when the error is a ZodError', () => {
      // Act & Assert
      expect(toMessage(new ZodError([]))).toContain('サーバーの応答形式');
    });

    it('should return the network message when the error is unknown', () => {
      // Act & Assert
      expect(toMessage(new TypeError('Failed to fetch'))).toContain('サーバーに接続できませんでした');
    });
  });

  describe('isUnauthorized', () => {
    it.each([
      [401, true],
      [403, false],
      [500, false],
    ])('should judge status %i as %s', (status, expected) => {
      // Act & Assert
      expect(isUnauthorized(new ApiError(status, 'error'))).toBe(expected);
    });
  });
});
```

### `frontend/src/api/auth.ts`

```typescript
/** 認証関連のAPI呼び出し。 */

import { clearCsrfToken, request, requestVoid, storeCsrfToken } from './client';
import { loginResponseSchema, userSchema, type User } from './schemas';

export function registerUser(username: string, password: string): Promise<User> {
  return request('/users', userSchema, { method: 'POST', body: { username, password } });
}

export async function login(username: string, password: string): Promise<User> {
  const result = await request('/login', loginResponseSchema, {
    method: 'POST',
    body: { username, password },
  });

  storeCsrfToken(result.csrf_token);

  return result.user;
}

export async function logout(): Promise<void> {
  await requestVoid('/logout', { method: 'POST', csrf: true });

  clearCsrfToken();
}

export function fetchCurrentUser(): Promise<User> {
  return request('/users/me', userSchema);
}
```

### `frontend/src/api/messages.ts`

```typescript
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
```

---

## 10-6. 状態管理フックを実装する

APIの呼び出しと画面の状態を結ぶ層。ここを分けておくと、コンポーネントは「受け取った値を表示するだけ」に保てる。

### `frontend/src/hooks/useAuth.ts`

```typescript
/**
 * 認証状態を保持し、ログイン／登録／ログアウトとセッション復元を提供するフック。
 */

import { useCallback, useEffect, useState } from 'react';

import * as authApi from '../api/auth';
import { clearCsrfToken, getCsrfToken } from '../api/client';
import { isUnauthorized, toMessage } from '../api/errors';
import type { User } from '../api/schemas';

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

export interface UseAuthResult {
  readonly status: AuthStatus;
  readonly user: User | null;
  /** 起動時のセッション復元で表示すべきメッセージ。無ければnull */
  readonly bootstrapNotice: string | null;
  readonly login: (username: string, password: string) => Promise<void>;
  readonly register: (username: string, password: string) => Promise<void>;
  readonly logout: () => Promise<void>;
  /** セッション切れを検知したときにログイン画面へ戻す */
  readonly expire: () => void;
}

export function useAuth(): UseAuthResult {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<User | null>(null);
  const [bootstrapNotice, setBootstrapNotice] = useState<string | null>(null);

  // 再読み込み時のセッション復元。
  // Session CookieはHttpOnlyでJSからは読めないため、/api/users/me を叩いて判定する。
  useEffect(() => {
    let cancelled = false;

    async function restore(): Promise<void> {
      try {
        const current = await authApi.fetchCurrentUser();

        if (cancelled) {
          return;
        }

        // Cookieはあるが、このタブのsessionStorageにCSRFトークンが無い場合
        // （別タブで開いた等）は、状態変更APIが必ず403になるためログイン画面へ戻す。
        if (getCsrfToken() === null) {
          setStatus('anonymous');
          setBootstrapNotice('操作を続けるにはログインし直してください。');
          return;
        }

        setUser(current);
        setStatus('authenticated');
      } catch (error: unknown) {
        if (cancelled) {
          return;
        }

        clearCsrfToken();
        setStatus('anonymous');

        // 未ログイン(401)は正常な状態なのでエラー表示しない
        if (!isUnauthorized(error)) {
          setBootstrapNotice(toMessage(error));
        }
      }
    }

    void restore();

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string): Promise<void> => {
    const authenticated = await authApi.login(username, password);

    setUser(authenticated);
    setStatus('authenticated');
    setBootstrapNotice(null);
  }, []);

  const register = useCallback(async (username: string, password: string): Promise<void> => {
    // 登録APIはログイン状態にしないため、呼び出し側で続けてloginする
    await authApi.registerUser(username, password);
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    await authApi.logout();

    setUser(null);
    setStatus('anonymous');
  }, []);

  const expire = useCallback((): void => {
    clearCsrfToken();
    setUser(null);
    setStatus('anonymous');
  }, []);

  return { status, user, bootstrapNotice, login, register, logout, expire };
}
```

> `cancelled` フラグは、レスポンスが返る前にコンポーネントが破棄された場合に `setState` を呼ばないためのもの。開発時の `StrictMode` は意図的にeffectを2回実行するため、これが無いと状態更新が二重になる。

### `frontend/src/hooks/useMessages.ts`

```typescript
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
```

---

## 10-7. UIコンポーネントを実装する

STEP 9 の `ui.js` が担っていた描画を、状態を受け取って表示を返すコンポーネントへ分解する。

> **XSS対策について。** JSXは埋め込んだ文字列を自動でエスケープするため、STEP 9 で `textContent` を使って手動で守っていた部分は言語機能として保証される。逆に言えば、`dangerouslySetInnerHTML` を使った瞬間にその保証が消える。このアプリでは使わない。

### `frontend/src/components/Notice.tsx`

```typescript
export type NoticeKind = 'error' | 'success';

export interface NoticeState {
  readonly message: string;
  readonly kind: NoticeKind;
}

interface NoticeProps {
  readonly notice: NoticeState | null;
}

export function Notice({ notice }: NoticeProps) {
  if (notice === null) {
    return null;
  }

  return (
    // エラーはalertとして即座に読み上げ、成功通知はstatusとして控えめに伝える
    <p className="notice" data-kind={notice.kind} role={notice.kind === 'error' ? 'alert' : 'status'}>
      {notice.message}
    </p>
  );
}
```

### `frontend/src/components/Header.tsx`

```typescript
interface HeaderProps {
  readonly username: string | null;
  readonly disabled: boolean;
  readonly onLogout: () => void;
}

export function Header({ username, disabled, onLogout }: HeaderProps) {
  return (
    <header className="header">
      <h1 className="header__title">Web Practice</h1>

      {username !== null && (
        <div className="header__user">
          <span>{username}</span>
          <button type="button" className="button" disabled={disabled} onClick={onLogout}>
            ログアウト
          </button>
        </div>
      )}
    </header>
  );
}
```

### `frontend/src/components/AuthPanel.tsx`

入力値の検証属性（`minLength` / `maxLength` / `pattern`）は STEP 9 と同じく、バックエンドの `UserCreate` の制約に合わせる。**HTML側の検証はUXのためであり、セキュリティ境界ではない**点も変わらない。

```typescript
import { useState, type FormEvent, type MouseEvent } from 'react';

interface AuthPanelProps {
  readonly disabled: boolean;
  /** 成功した場合にtrueを返す。パスワード欄をクリアするかの判断に使う */
  readonly onLogin: (username: string, password: string) => Promise<boolean>;
  readonly onRegister: (username: string, password: string) => Promise<boolean>;
}

export function AuthPanel({ disabled, onLogin, onRegister }: AuthPanelProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  async function submit(action: (u: string, p: string) => Promise<boolean>): Promise<void> {
    const succeeded = await action(username, password);

    if (succeeded) {
      setPassword('');
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();

    void submit(onLogin);
  }

  function handleRegister(event: MouseEvent<HTMLButtonElement>): void {
    // type="button" ではブラウザの検証属性が自動実行されないため明示的に呼ぶ
    const form = event.currentTarget.form;

    if (form !== null && !form.reportValidity()) {
      return;
    }

    void submit(onRegister);
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="form__label" htmlFor="username">
        ユーザー名
      </label>
      <input
        className="form__input"
        id="username"
        name="username"
        type="text"
        required
        minLength={3}
        maxLength={50}
        pattern="[A-Za-z0-9_-]+"
        autoComplete="username"
        disabled={disabled}
        value={username}
        onChange={(event) => setUsername(event.target.value)}
      />

      <label className="form__label" htmlFor="password">
        パスワード
      </label>
      <input
        className="form__input"
        id="password"
        name="password"
        type="password"
        required
        minLength={8}
        maxLength={128}
        autoComplete="current-password"
        disabled={disabled}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />

      <div className="form__actions">
        <button className="button button--primary" type="submit" disabled={disabled}>
          ログイン
        </button>
        <button className="button" type="button" disabled={disabled} onClick={handleRegister}>
          新規登録
        </button>
      </div>
    </form>
  );
}
```

### `frontend/src/components/MessageForm.tsx`

```typescript
import { useState, type FormEvent } from 'react';

interface MessageFormProps {
  readonly disabled: boolean;
  /** 成功した場合にtrueを返す。失敗時に入力内容を失わせないため */
  readonly onSubmit: (text: string) => Promise<boolean>;
}

export function MessageForm({ disabled, onSubmit }: MessageFormProps) {
  const [text, setText] = useState('');

  async function submit(): Promise<void> {
    const succeeded = await onSubmit(text);

    if (succeeded) {
      setText('');
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();

    void submit();
  }

  return (
    <form className="form form--inline" onSubmit={handleSubmit}>
      <input
        className="form__input"
        id="message-text"
        name="text"
        type="text"
        required
        maxLength={255}
        placeholder="メッセージを入力"
        disabled={disabled}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />
      <button className="button button--primary" type="submit" disabled={disabled}>
        追加
      </button>
    </form>
  );
}
```

### `frontend/src/components/MessageItem.tsx`

```typescript
import type { Message } from '../api/schemas';

interface MessageItemProps {
  readonly message: Message;
  readonly disabled: boolean;
  readonly onArchive: (messageId: number) => void;
}

export function MessageItem({ message, disabled, onArchive }: MessageItemProps) {
  const className = message.is_archived ? 'message message--archived' : 'message';

  return (
    <li className={className}>
      {/* JSXが文字列を自動エスケープするため、HTMLとしては解釈されない */}
      <span className="message__text">{message.text}</span>

      <time className="message__time" dateTime={message.created_at}>
        {new Date(message.created_at).toLocaleString('ja-JP')}
      </time>

      {/* アーカイブ済みには再度アーカイブするボタンを出さない */}
      {!message.is_archived && (
        <button
          type="button"
          className="button"
          disabled={disabled}
          onClick={() => onArchive(message.id)}
        >
          アーカイブ
        </button>
      )}
    </li>
  );
}
```

### `frontend/src/components/MessageList.tsx`

```typescript
import type { Message } from '../api/schemas';
import { MessageItem } from './MessageItem';

interface MessageListProps {
  readonly messages: readonly Message[];
  readonly disabled: boolean;
  readonly onArchive: (messageId: number) => void;
}

export function MessageList({ messages, disabled, onArchive }: MessageListProps) {
  if (messages.length === 0) {
    return <p className="message-list__empty">メッセージはまだありません。</p>;
  }

  return (
    <ul className="message-list">
      {messages.map((message) => (
        // keyは配列のindexではなくidを使う。並び替えや削除で表示がずれるのを防ぐ
        <MessageItem key={message.id} message={message} disabled={disabled} onArchive={onArchive} />
      ))}
    </ul>
  );
}
```

### コンポーネントのテスト

`frontend/src/components/MessageList.test.tsx`。STEP 9 で手動確認していたXSS対策を、テストとして固定できるのがReact化の利点のひとつ。

```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { buildMessage } from '../../tests/factories/models';
import { MessageList } from './MessageList';

describe('MessageList', () => {
  it('should render the empty state when there are no messages', () => {
    // Arrange & Act
    render(<MessageList messages={[]} disabled={false} onArchive={vi.fn()} />);

    // Assert
    expect(screen.getByText('メッセージはまだありません。')).toBeInTheDocument();
  });

  it('should render the raw text when the message contains HTML', () => {
    // Arrange
    const message = buildMessage({ text: '<img src=x onerror=alert(1)>' });

    // Act
    render(<MessageList messages={[message]} disabled={false} onArchive={vi.fn()} />);

    // Assert
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
  });

  it('should call onArchive with the message id when the archive button is clicked', async () => {
    // Arrange
    const message = buildMessage();
    const onArchive = vi.fn();
    render(<MessageList messages={[message]} disabled={false} onArchive={onArchive} />);

    // Act
    await userEvent.click(screen.getByRole('button', { name: 'アーカイブ' }));

    // Assert
    expect(onArchive).toHaveBeenCalledWith(message.id);
  });

  it('should not render the archive button when the message is already archived', () => {
    // Arrange
    const message = buildMessage({ is_archived: true });

    // Act
    render(<MessageList messages={[message]} disabled={false} onArchive={vi.fn()} />);

    // Assert
    expect(screen.queryByRole('button', { name: 'アーカイブ' })).not.toBeInTheDocument();
  });
});
```

他のコンポーネントについても、最低限このあたりを押さえておくとよい。

| 対象 | テストすること |
| --- | --- |
| `Notice` | `notice` が `null` のとき何も描画しない／`kind` によって `role` が変わる |
| `AuthPanel` | ログイン成功時にパスワード欄がクリアされる／失敗時は保持される |
| `MessageForm` | 送信成功時に入力欄がクリアされる／`disabled` の間は送信できない |
| `Header` | 未ログイン時にログアウトボタンを描画しない |

```bash
pnpm test
```

---

## 10-8. アプリを組み立てる

### `frontend/src/styles/global.css`

10-3 で `git mv` した STEP 9 のCSSをそのまま使う。クラス名はコンポーネントの `className` と一致させてあるため、追記は読み込み中表示の1つだけ。

```css
.loading {
  color: var(--color-muted);
}
```

### `frontend/src/App.tsx`

エラーハンドリングと画面の出し分けを担う。STEP 9 の `main.js` に相当する層。

```typescript
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
          setNotice({ message: 'セッションが切れました。ログインし直してください。', kind: 'error' });

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
    notice ?? (bootstrapNotice === null ? null : { message: bootstrapNotice, kind: 'error' as const });

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
```

> `runAction` の依存配列に `expire` と `clear` だけを入れているのは、これらが `useCallback` で安定しているため。フックが返すオブジェクト（`useAuth()` の戻り値そのもの）を依存に入れると、レンダリングのたびに新しい参照になり `useCallback` が無意味になる。

### `frontend/src/main.tsx`

```typescript
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import './styles/global.css';

const container = document.getElementById('root');

// index.html に #root が無い状態は設定ミス。黙って無視せず即座に失敗させる
if (container === null) {
  throw new Error('Root element (#root) not found in index.html');
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

### 品質チェック

```bash
cd frontend

pnpm typecheck
pnpm lint
pnpm format
pnpm test
```

---

## 10-9. 開発サーバーで動作確認する

APIは Caddy 経由で叩くので、先にバックエンドを起動しておく。

```bash
# リポジトリルートで
docker compose --env-file ./backend/.env up -d backend db caddy

curl -i http://localhost/api/health   # → 200 OK
```

Vite の開発サーバーを起動する。

```bash
cd frontend
pnpm dev
```

`http://localhost:5173/` を開いて、STEP 9 と同じ操作が一通りできることを確認する。

- ログインフォームが表示される
- 新規登録 → メッセージ画面へ遷移
- メッセージの追加・アーカイブ
- 再読み込みでログイン状態が復元される
- ログアウト

> **`http://localhost:5173` と `http://localhost` は別オリジン。**
> Cookieはポートを区別しないので `session` は両方で送られるが、**`sessionStorage` はオリジン単位**なのでCSRFトークンは共有されない。
> 開発サーバーでログインしたあと `http://localhost/` を開くと「操作を続けるにはログインし直してください」と出るのはこのため。壊れているわけではない。確認は片方のオリジンに統一して行う。

ファイルを編集して保存し、ブラウザが自動更新されること（HMR）も確認しておく。

---

## 10-10. ビルド成果物をCaddyから配信する

### `frontend/Dockerfile`

`backend/Dockerfile` と同じく、ビルド環境と実行環境を分ける多段構成にする。最終ステージが `caddy` イメージそのものになるため、Caddyの設定や証明書の扱いは今までどおり。

```dockerfile
# syntax=docker/dockerfile:1

# ----------------------------------------------
# Builder stage
# 依存のインストールとViteのビルドを行う。Nodeはこのステージにしか残らない
# ----------------------------------------------

FROM node:24-bookworm-slim AS builder

WORKDIR /app

# CorepackがpackageManagerフィールドのpnpmを取得する。
# 非対話環境ではダウンロード確認プロンプトが出るため無効化する
ENV PNPM_HOME=/pnpm
ENV PATH="${PNPM_HOME}:${PATH}"
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0

RUN corepack enable pnpm

# 依存だけ先に入れてレイヤーをキャッシュする。ソース変更で再インストールが走らない
COPY package.json pnpm-lock.yaml ./

RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile

COPY . .

# typecheck も通す（package.json の build スクリプト）
RUN pnpm build

# ----------------------------------------------
# Runtime stage
# ビルド成果物だけをCaddyイメージへ載せる
# ----------------------------------------------

FROM caddy:2-alpine AS runtime

COPY --from=builder /app/dist /srv/frontend
```

> `--frozen-lockfile` は、`pnpm-lock.yaml` と `package.json` が食い違っていたらビルドを失敗させるオプション。ロックファイルを更新し忘れたままイメージだけ別バージョンで作られる事故を防ぐ。
> Corepackが使えないNodeイメージを使う場合は `RUN npm install -g pnpm@10.33.4` に置き換える。

### `compose.yaml`

`caddy` サービスを、既製イメージの利用からビルドへ切り替える。`./frontend` のバインドマウントは削除する。

```yaml
  caddy:
    # フロントエンドのビルド成果物を同梱したCaddyイメージを作る（frontend/Dockerfile を参照）
    build:
      context: ./frontend
      target: runtime
    ports:
      - "80:80"
      - "443:443"
    volumes:
      # Caddyfileはマウントのまま。再ビルドせずに reload できる
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - backend
    restart: unless-stopped
```

変更点は3つ。

1. `image: caddy:2-alpine` を `build:` へ置き換える
2. `- ./frontend:/srv/frontend:ro` を**削除**する（これでソースが配信される問題も消える）
3. `Caddyfile` のマウントは残す

> 証明書は `caddy_data` という named volume にあるため、イメージを作り直しても再取得されない。

### `Caddyfile`

配信元のパス（`/srv/frontend`）は変わらないので、必須の変更は無い。ただしViteの成果物はファイル名にハッシュが入るので、キャッシュ設定を入れておくと効果が大きい。

```caddyfile
# フロントエンド + API（同一オリジン）
taph-lab.com {
    encode gzip zstd

    handle /api/* {
        reverse_proxy backend:8000
    }

    handle {
        root * /srv/frontend

        # Viteの成果物はファイル名にハッシュが入るため、内容が変われば必ず名前も変わる。
        # よって長期キャッシュしてよい
        @assets path /assets/*
        header @assets Cache-Control "public, max-age=31536000, immutable"

        # index.html は毎回検証させる。ここが古いままだと新しいハッシュ名を拾えない
        @entry not path /assets/*
        header @entry Cache-Control "no-cache"

        try_files {path} /index.html
        file_server
    }
}
```

`http://localhost` のブロックにも同じ内容を入れる。`api.taph-lab.com` のブロックは変更なし。

`try_files {path} /index.html` は STEP 9 から入れてある。React Router などのクライアントサイドルーティングを後から足す場合、この行がそのまま効く。

### Makefile（任意）

フロントエンドの反映を1コマンドにしておくと楽になる。**レシピ行の行頭はスペースではなくタブ**である必要がある。

<!-- markdownlint-disable MD010 -->

```makefile
.PHONY: setup setup-network setup-volumes chowns up-dev down-dev exec-dev up build-front

# フロントエンドをビルドし直してCaddyへ反映する
build-front:
	docker compose --env-file ./backend/.env build caddy
	docker compose --env-file ./backend/.env up -d caddy
```

<!-- markdownlint-enable MD010 -->

### ビルドと反映

```bash
# リポジトリルートで
docker compose --env-file ./backend/.env build caddy
docker compose --env-file ./backend/.env up -d caddy

# 設定ファイルの文法チェック
docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile

# イメージの中に成果物が入っているか
docker compose exec caddy ls /srv/frontend

curl -i http://localhost/            # → 200, Content-Type: text/html
curl -i http://localhost/api/health  # → 200, {"status":"ok"}
```

`ls /srv/frontend` に `index.html` と `assets/` があればよい。ブラウザで `http://localhost/` を開いて画面が出れば、ここまで完了。

---

## 10-11. 公開する

DNSとドメインは STEP 9 で設定済みなので、追加の設定は不要。

### サーバーへ反映する

OCI VM 上で次を実行する。

```bash
git pull

# フロントエンドを同梱したCaddyイメージを作り直す
docker compose --env-file ./backend/.env build caddy
docker compose --env-file ./backend/.env up -d caddy
```

**サーバー側に Node や pnpm を入れる必要は無い。** ビルドはDockerのbuilderステージの中で完結する。

> OCI無料枠のVMはメモリが小さい。`vite build` が OOM で落ちる場合は、ローカルでイメージを作ってレジストリ経由で配る形にする。これは STEP 11（CI/CD）でGitHub Actionsに任せる部分でもある。

### 反映を確認する

```bash
curl -I https://taph-lab.com/
docker compose logs caddy | tail -20
```

`COOKIE_SECURE=true` は STEP 9 で設定済み。変更していなければそのままでよい。

---

## 10-12. 動作確認

### ブラウザでの確認

`https://taph-lab.com/`（ローカルなら `http://localhost/`）を開いて次を順に確認する。STEP 9 の確認項目と同じ。

| # | 操作 | 期待する結果 |
| --- | --- | --- |
| 1 | 初期表示 | 一瞬「読み込み中…」が出た後、ログインフォームが表示される |
| 2 | 3文字未満のユーザー名で「新規登録」 | ブラウザの検証メッセージが出て送信されない |
| 3 | 有効な情報で「新規登録」 | 登録成功メッセージ → メッセージ画面へ遷移 |
| 4 | 同じユーザー名でもう一度「新規登録」 | `Username already exists` が表示され、パスワード欄は消えない |
| 5 | メッセージを入力して「追加」 | 一覧に追加され、入力欄がクリアされる |
| 6 | 「アーカイブ」 | 取り消し線が付き、ボタンが消える |
| 7 | ページを再読み込み（F5） | ログイン状態と一覧が復元される |
| 8 | 「ログアウト」 | ログインフォームに戻る |
| 9 | ログアウト後に再読み込み | ログインフォームのまま（エラーは出ない） |
| 10 | 誤ったパスワードでログイン | `Invalid username or password` が表示される |
| 11 | 送信中の連打 | ボタンと入力欄が一時的に無効化され、二重送信されない |

### DevToolsでの確認

#### Networkタブ

- `POST /api/login` のレスポンスヘッダーに `Set-Cookie: session=...; HttpOnly; SameSite=lax`（公開環境ではさらに `Secure`）
- `POST /api/messages` のリクエストヘッダーに `X-CSRF-Token`
- `GET /` のあとに `/assets/index-<ハッシュ>.js` と `/assets/index-<ハッシュ>.css` が `200`
- `/assets/*` のレスポンスヘッダーに `Cache-Control: public, max-age=31536000, immutable`

#### Applicationタブ

- Cookies に `session` があり `HttpOnly` にチェック
- Session Storage に `csrfToken`

#### Consoleタブ

- エラーが出ていないこと

### XSS対策の確認

メッセージ本文に次を入力して追加する。

```text
<img src=x onerror=alert(1)>
```

アラートが出ず、入力した文字列がそのまま表示されれば正しい。10-7 で書いたテストが同じことを自動で確認している。

### コード品質の確認

```bash
cd frontend

pnpm typecheck
pnpm lint
pnpm format:check
pnpm test
pnpm test:coverage
```

バックエンド側に変更は入れていないが、念のため通しておく。

```bash
cd backend
uv run pytest
```

---

## 10-13. ドキュメントを更新する

### `README.md`

以下を更新する。

| 箇所 | 変更内容 |
| --- | --- |
| Tech Stack | フロントエンドの行を追加（TypeScript / React / Vite / pnpm / Vitest / ESLint + Prettier / Zod） |
| Architecture > Runtime | Caddyが静的ファイルとAPIを振り分ける構成図に更新する |
| Repository layout | `frontend/` を 10-1 のディレクトリ構成に差し替える |
| Getting Started | フロントエンドの開発コマンド（`pnpm dev` / `pnpm test` など）の節を追加する |
| STEP > 完了 | STEP 9 と STEP 10 を「完了」の表へ移す |
| Documentation | 変更なし |

**あわせて既存のリンク切れを直す。** 現在の README は STEP 9 の手順書を `docs/guides/static-frontend.md` として参照しているが、実際のファイル名は `docs/guides/step09-static-frontend.md`。

```bash
grep -n "static-frontend" README.md
```

### `CLAUDE.md`

`Project Structure` のフロントエンドの記述を具体化する。

```markdown
- フロントエンド: `frontend/`
  - ソースコード: `frontend/src/`
  - ユニットテスト: ソースと同階層にコロケーション（`*.test.ts` / `*.test.tsx`）
  - テストセットアップ・factory: `frontend/tests/`
```

### 後片付け

設定ファイルの移植が終わったら、持ち込み元のディレクトリを削除する。

```bash
rm -rf frontend/.tmp
```

`.tmp/` は `.gitignore` 済みなのでコミットには影響しないが、`frontend/.dockerignore` にも入れてあるとおり、イメージへ紛れ込ませない意味でも消しておく。

---

## 発展: CSRFトークンの再発行（任意）

STEP 9 の「既知の制約」で先送りにした問題への対応。**このガイドの範囲外だが、STEP 10 と合わせて実施すると体験が改善する。**

現状のバックエンドは**ログイン時にしかCSRFトークンを発行しない**ため、新しいタブで開いた場合や、開発サーバーと本番URLを行き来した場合に「Cookieはあるがトークンが無い」状態になる。

### バックエンド側

`backend/src/web_practice/routers/auth.py` に、現在のセッションのCSRFトークンを**新しく発行し直す**エンドポイントを追加する。DBにはハッシュしか保存していないため、元のトークンを取り出すことはできず、ローテーションする形になる。

```python
@router.post("/auth/csrf", response_model=CsrfTokenResponse)
def refresh_csrf(
    auth_session: CurrentAuthSession,
    db: DbSession,
) -> CsrfTokenResponse:
    """現在のセッションに対して新しいCSRFトークンを発行する。"""
    csrf_token = generate_csrf_token()

    auth_session.csrf_token_hash = hash_csrf_token(csrf_token)
    db.commit()

    return CsrfTokenResponse(csrf_token=csrf_token)
```

TDDの順序で、先に `backend/tests/routers/test_auth.py` へ次のケースを追加する。

- 未ログインでは401を返す
- ログイン済みなら200と新しいトークンを返す
- 発行後、古いトークンでは状態変更APIが403になる
- 発行後、新しいトークンでは状態変更APIが成功する

### フロントエンド側

`useAuth` のセッション復元で、トークンが無ければ取得しにいく。

```typescript
if (getCsrfToken() === null) {
  storeCsrfToken(await authApi.refreshCsrfToken());
}
```

### この方式のトレードオフ

ローテーション方式では、**複数タブを同時に開くと後から開いたタブが先のタブのトークンを無効化する**。1タブ運用なら問題にならないが、気になる場合は Double Submit Cookie 方式（ログイン時にCSRFトークンを `HttpOnly` でないCookieにも入れ、JSがそれを読んでヘッダーへ載せる）のほうが素直。`sessionStorage` が不要になり、タブ間の共有も自然に解決する。

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| `pnpm: command not found` | pnpm未導入 | `corepack enable pnpm`（10-2） |
| `pnpm install` が `ERR_PNPM_UNSUPPORTED_ENGINE` | Nodeが古い | Node 20以上にする |
| `pnpm dev` で `/api/*` が `ECONNREFUSED` | Caddyが起動していない | `docker compose ps` で確認し `up -d caddy` |
| `pnpm dev` で `/api/*` が404 | proxyのtargetが違う／Caddyのサイトブロックにマッチしていない | `vite.config.ts` の `target` と `changeOrigin: true` を確認 |
| 5173でログインしたのに80でメッセージ追加が403 | `sessionStorage` はオリジン単位。ポートが違えば別オリジン | 確認するオリジンを統一する（10-9） |
| `import.meta.env` が型エラー | `types: ["vite/client"]` が無い | `tsconfig.json` を確認（10-3） |
| `Cannot find name 'document'` | `lib` に `DOM` が無い | `tsconfig.json` の `lib` を確認 |
| `'X' is a type and must be imported using a type-only import` | `verbatimModuleSyntax: true` | `import type { X } from ...` に直す |
| ESLintが `'document' is not defined` | `globals.browser` の指定漏れ | `eslint.config.js` の `languageOptions.globals` |
| `Cannot find package 'jsdom'` | jsdom未導入 | `pnpm add -D jsdom` |
| `toBeInTheDocument is not a function` | jest-domのマッチャ未登録 | `tests/setup.ts` と `setupFiles` の指定を確認 |
| 開発中に同じAPIが2回呼ばれる | `StrictMode` が意図的にeffectを2回実行する | 開発時のみの挙動。本番ビルドでは起きない |
| `pnpm build` が成功するのにブラウザが白い | 型は通ったが実行時エラー | Consoleのスタックトレースを確認。`#root` の有無も確認 |
| Caddy経由で古い画面が出る | イメージを作り直していない | `docker compose build caddy && docker compose up -d caddy` |
| `/` で `package.json` が見える | `./frontend` のバインドマウントが残っている | `compose.yaml` から削除する（10-10） |
| Dockerビルドが `ERR_PNPM_OUTDATED_LOCKFILE` | `package.json` と `pnpm-lock.yaml` の不整合 | ホストで `pnpm install` してロックファイルをコミットする |
| Dockerビルドが `/app/dist not found` | `pnpm build` が失敗している | `docker compose build caddy --progress=plain` でログを見る |
| ビルドがOOMで落ちる（サーバー） | メモリ不足 | ローカルでビルドしてイメージを配る（STEP 11で自動化） |

---

## 既知の制約

### CSRFトークンとオリジン／タブの関係

STEP 9 から引き継いだ制約。バックエンドがログイン時にしかCSRFトークンを発行しないため、`sessionStorage` に持っている。

```text
同じオリジンで再読み込み(F5)
  → Cookie ○  sessionStorage ○  → 正常に復元される

別タブで同じURLを開く / 5173と80を行き来する
  → Cookie ○  sessionStorage ✗  → ログイン済みだが状態変更ができない
```

`useAuth` の復元処理が後者を検出して「ログインし直してください」と表示する。**発生しても壊れないが、体験としては良くない。** 恒久対応は「発展」の節を参照。

### ビルドが必要になった

`frontend/` を直接編集してもサーバーには反映されない。`docker compose build caddy` を通す必要がある。開発中のフィードバックループが `pnpm dev` に移った代わりに、**反映漏れという新しい失敗モードが増えた**。STEP 11 でCI/CDに載せて自動化する対象。

### Viteの環境変数は秘密を置けない

`import.meta.env.VITE_*` はビルド時にコードへ埋め込まれ、配信されるJSにそのまま現れる。**APIキーなどの秘密情報は絶対に置かない。** このアプリはAPIを同一オリジンの `/api` 固定で叩くため、そもそも環境変数を使っていない。

### HTMLの検証はセキュリティではない

`minLength` や `pattern` はUXのための機能で、DevToolsから簡単に外せる。実際の防御はPydanticスキーマによるサーバー側の検証が担う。この点は STEP 9 から変わらない。

### 更新のたびに一覧を取り直している

`useMessages` は作成・アーカイブのたびに `GET /api/messages` を呼ぶ。件数が増えると無駄が目立つ。TanStack Query などのキャッシュ層や楽観的更新の導入が次の一手になるが、このSTEPでは「サーバーの状態と画面が必ず一致する」ことを優先した。

---

## STEP 11（CI/CD）への引き継ぎ

この構成は、GitHub Actionsへそのまま載せられるように作ってある。

| 項目 | STEP 10（現在） | STEP 11（CI/CD） |
| --- | --- | --- |
| バックエンドのテスト | `uv run pytest` を手で実行 | pushごとにCIで実行 |
| フロントエンドの検証 | `pnpm typecheck && pnpm lint && pnpm test` を手で実行 | 同上。ジョブを分けて並列実行できる |
| イメージのビルド | サーバー上で `docker compose build` | CIでビルドしてレジストリへpush |
| デプロイ | サーバーで `git pull` + `build` + `up -d` | CIからイメージをpullして差し替え |
| Migration | 手動で `alembic upgrade head` | デプロイ手順に組み込む |

`frontend/Dockerfile` の builder ステージがそのままCIのビルドステップになるため、**「CIでだけ壊れる」状態を作りにくい**。ローカルで `docker compose build caddy` が通ればCIでも通る。

---

## 導入記録

この手順書に沿った導入記録。

| # | 手順 | ステータス | コミット |
| --- | --- | --- | --- |
| 10-1 | ゴールと構成を確認する | 完了 | - |
| 10-2 | Node と pnpm を用意する | 完了 | 83bb2d44fb23239742b11d49b744acedb0175ed8 |
| 10-3 | Viteプロジェクトの雛形を作る | 完了 (一部変更あり) | 1f0e22dd43f0bed6f6e0d565c0e5e13083991f9a |
| 10-4 | テスト環境を整える | 完了 | 33114e046f6f126cbf81a904d8d59f9da1d54d3f |
| 10-5 | APIクライアントを実装する | 完了 | 6098906f9ab391e4020707e7a5a12a1ede1de017 |
| 10-6 | 状態管理フックを実装する | 完了 | 29650138380bfe655904b2f37faede5e068da6d2 |
| 10-7 | UIコンポーネントを実装する | 完了 | f26df1c3ff41d67a608714b008dc957224258871 |
| 10-8 | アプリを組み立てる | 完了 | 01fb7d9bea5bd1926c614dbf613aca3fcb875bed |
| 10-9 | 開発サーバーで動作確認する | 完了 | - |
| 10-10 | ビルド成果物をCaddyから配信する | 完了 | 37366f0b7476d7301cda0308ade1be5109809079 |
| 10-11 | 公開する | 未着手 | - |
| 10-12 | 動作確認 | 未着手 | - |
| 10-13 | ドキュメントを更新する | 未着手 | - |

追記:

- 10-3の`tsconfig.json`で`noUncheckedIndexedAccess`を`false`にしているが、型安全性を高めるため`true`に変更した。
- 10-3で、現状の最新のTypeScript7.0.3はコンパイラAPIを同梱せず、eslintが動しないため `frontend/package.json` で typescriptを6.0.3に固定している。TypeScript7.1で解消予定。 (コミット: 65ad19b0150ecc39f526388fe242905abc3a4fa2)
