---
name: code-review
description: |
  コードレビューを実行する。コードを書いた後や変更した後に必ず使用する。
  「/code-review」で直近の実装、「/code-review {ファイルパス}」で特定のファイルをレビューする。
context: fork
agent: code-reviewer
---

# Code Review Skill

コードの品質、セキュリティ、保守性を確保するためのコードレビューを実行。

---

## レビュープロセス

### Step 1: レビュー対象ファイルの特定

$ARGUMENTS にパスが渡された場合はそのファイルを対象にする。
$ARGUMENTS が空の場合は、下記の手順で変更されたファイルを特定する：

```bash
# 新規ファイルをgit diffで確認できるようにgit管理下に追加する
git add --intent-to-add .

# 作業ディレクトリ-ローカルリポジトリの差分を確認
git diff --name-only HEAD
```

### Step 2: 言語別レビュールール追加

変更ファイルの拡張子ごとに、該当するレビュールールを Read して追加する。

| 拡張子 | 言語別レビュールール | 言語名 |
| --- | --- | --- |
| .ts .tsx | `.claude/rules/typescript-review-guide.md` | TypeScript |
| .js .jsx | `.claude/rules/typescript-review-guide.md` | JavaScript |
| .py | `.claude/rules/python-review-guide.md` | Python |

### Step 3: レビュー実施

- `.claude/rules/code-review-guide.md` の共通ルールと言語別ルールを基に対象ファイルをレビューする
- CRITICALからLOWまでの各カテゴリを順番に確認する
- レビュー時に、下記のフォーマットで進捗を提示する

```text
## レビュー実施 ({N} Files)

- [ ] {言語名}: {ファイルパス}
- [ ] {言語名} {ファイルパス}
...

```

### Step 4: 所見の報告

レビュー結果を後述のフィルタリングを行った上、下記のフォーマットを使用して優先度順にリストアップし報告する。

```text
## Review Summary

| 優先度 | ファイルパス:行数 | 内容 |
| --- | --- | --- |
| HIGH | `src/xxx.py:10` | 大きすぎる関数（110行） |
| HIGH | `src/yyy.py:25` | 深いネスト（5段） |
| LOW | `src/zzz.py:30` |  |

Verdict:
  WARNING — HIGH 2ファイル -> マージ前に解決することを推奨
```
---

## 優先度の定義

| 優先度 | 意味 | 対応 |
| --- | --- | --- |
| CRITICAL | セキュリティ脆弱性またはデータ損失のリスク | **BLOCK** - 修正するまでマージ不可 |
| HIGH | バグまたは重大な品質問題 | **WARN** - 原則マージ前に修正 |
| MEDIUM | 保守性の懸念 | **INFO** - 修正を検討 |
| LOW | スタイルや軽微な指摘 | **NOTE** - 任意 |

---

## 承認基準

- **Approve**：CRITICALおよびHIGH問題がない場合
- **Warning**：HIGH問題のみの場合（注意の上マージ可）
- **Block**：CRITICAL問題が見つかった場合 — マージ前に必ず修正すること

---

## 報告項目のフィルタリング

レビュー結果にノイズを増やさないように、以下のフィルターを適用：

- **報告**：80%以上の確信がある問題
- **優先**：バグ・セキュリティ・データ損失につながる問題
- **統合**：類似問題（例：「5箇所でエラーハンドリング不足」）
- **スキップ**：単なるスタイル差（プロジェクト規約違反でない限り）
- **スキップ**：未変更コードの問題（CRITICALなセキュリティを除く）

