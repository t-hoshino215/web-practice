---
name: python-review-guide
description: Python ファイルのレビュー時に参照する追加基準
paths:
  - "**/*.py"
---

# Python Code Review Standards

Pythonらしいコードとベストプラクティスの高い基準を保証するコードレビュー基準を定義する。

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

- **SQLインジェクション**: クエリ内でのf文字列使用 → パラメータ化クエリを使用する
- **コマンドインジェクション**: シェルコマンドに未検証の入力 → `subprocess` をリスト引数で使用する
- **パストラバーサル**: ユーザー制御のパス → `normpath` で検証し `..` を拒否する
- **eval/execの乱用**、**安全でないデシリアライズ**、**ハードコードされた秘密情報**
- **弱い暗号**（セキュリティ用途でのMD5/SHA1）、**YAMLのunsafe load**

### CRITICAL: エラーハンドリング

- **裸のexcept**: `except: pass` → 具体的な例外を捕捉する
- **握りつぶされた例外**: サイレント失敗 → ログ出力して適切に処理する
- **コンテキストマネージャ未使用**: 手動のファイル/リソース管理 → `with` を使用する

### HIGH: 型ヒント

- 公開関数に型アノテーションがない
- `Any` を使っているが、より具体的な型が指定可能
- Nullableパラメータに `Optional` がない

### HIGH: Pythonらしい書き方（Pythonic）

- Cスタイルのループよりリスト内包表記を使用する
- `type() ==` ではなく `isinstance()` を使用する
- マジックナンバーではなく `Enum` を使用する
- ループ内の文字列連結ではなく `"".join()` を使用する
- **ミュータブルなデフォルト引数**: `def f(x=[])` → `def f(x=None)` を使用

### HIGH: コード品質

- 関数が50行超、または引数が5個超（dataclassの使用を検討）
- 深いネスト（4階層以上）
- 重複コードパターン
- 名前付き定数のないマジックナンバー

### HIGH: 並行処理

- ロックなしの共有状態 → `threading.Lock` を使用
- sync/asyncの不適切な混在
- ループ内でのN+1クエリ → バッチ処理にする

### MEDIUM: ベストプラクティス

- PEP 8: import順、命名、スペース
- 公開関数にdocstringがない
- `print()` の使用 → `logging` を使用
- 不要な `from module import *` → import範囲は最小限に
- `value == None` → `value is None` を使用
- 組み込み名の上書き（`list`, `dict`, `str` など）

---

## 診断コマンド

```bash
# リンティング
uv run ruff check .

# フォーマットチェック
uv run ruff format .

# 型チェック
uv run mypy .

# セキュリティチェック
uv run bandit -r .

# テストカバレッジ
pytest --cov=app --cov-report=term-missing
```
