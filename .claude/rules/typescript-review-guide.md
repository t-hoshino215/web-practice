---
name: typescript-review-guide
description: TypeScript/JavaScript ファイルのレビュー時に参照する追加基準
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
---

# TypeScript/JavaScript Code Review Standards

型安全性、非同期処理の正確性、Node/ウェブセキュリティとベストプラクティスの高い基準を保証するコードレビュー基準を定義する。

---

## 優先度の定義

| 優先度 | 意味 | 対応 |
| --- | --- | --- |
| CRITICAL | セキュリティ脆弱性またはデータ損失のリスク | **BLOCK** - 修正するまでマージ不可 |
| HIGH | バグまたは重大な品質問題 | **WARN** - 原則マージ前に修正 |
| MEDIUM | 保守性の懸念 | **INFO** - 修正を検討 |
| LOW | スタイルや軽微な指摘 | **NOTE** - 任意 |

---

## レビュー観点

### CRITICAL: セキュリティ

- `eval` / `new Function` によるインジェクション：ユーザー入力を実行しない
- XSS：未サニタイズ入力を `innerHTML` / `dangerouslySetInnerHTML` / `document.write` に代入
- SQL/NoSQLインジェクション：文字列結合ではなくプレースホルダやORMを使用
- パストラバーサル：`fs.readFile` や `path.join` にユーザー入力を使う場合は検証必須
- ハードコードされたシークレット：環境変数を使用
- プロトタイプ汚染：信頼できないオブジェクトのマージに注意
- `child_process` にユーザー入力：検証・許可リスト必須

### HIGH: 型安全性

- 不要な `any`：`unknown` または適切な型を使う
- 非nullアサーション（`!`）の乱用：事前チェックを追加
- `as` キャストの乱用：型を正しく定義する
- tsconfigの緩和：strict設定が弱められていれば指摘

### HIGH: 非同期の正しさ

- Promise未処理：`await` または `.catch()` を使用
- 独立処理の逐次await：`Promise.all` を検討
- 浮遊Promise：エラーハンドリングなしのfire-and-forget
- `forEach` + async：`for...of` または `Promise.all` を使う

### HIGH: エラーハンドリング

- エラーの握りつぶし：空の `catch`
- `JSON.parse` に try/catchなし
- Error以外のthrow：`throw new Error()`
- エラーバウンダリ不足（React）

### HIGH: イディオマティック

- 共有ミュータブル状態：不変データを優先
- `var` 使用：`const` / `let` を使う
- 戻り値型未指定：公開関数は明示
- コールバックとasync混在：Promiseに統一
- `==` の使用：`===` を使う

### HIGH: Node.js特有

- 同期fs：非同期版を使う
- 入力検証不足：zod等でスキーマ検証
- `process.env` 未検証
- ESMでの `require()` 混在

### MEDIUM: React / Next.js

- 依存配列不足（useEffect等）
- stateの直接変更
- indexをkeyに使用
- 派生stateをuseEffectで管理
- サーバ/クライアント境界の混在

### MEDIUM: パフォーマンス

- render内でのオブジェクト生成
- N+1クエリ
- memo化不足
- lodashの丸ごとimport

### MEDIUM: ベストプラクティス

- `console.log` の残存
- マジックナンバー
- 深いoptional chainingにfallbackなし
- 命名不一致

---

## 診断コマンド

```bash
# リンティング
pnpm eslint .

# フォーマットチェック
pnpm prettier --check .

# 型チェック
pnpm tsc --noEmit

# セキュリティチェック
pnpm audit

# テスト実行
pnpm vitest run

# テストカバレッジ
pnpm vitest run --coverage
```
