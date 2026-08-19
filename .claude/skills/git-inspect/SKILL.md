---
name: git-inspect
description: >
  git の変更履歴・コミット詳細・差分を調査するときに使うツール。
  「最近何が変わった？」「このコミットで何が変わった？」
  「どのファイルが変更された？」などの質問が来たら自動でロードする。
allowed-tools: Bash(uv run python .claude/skills/git-inspect/git_inspector.py *)
---

# git 調査スキル

## 使い方

このスキルを使うときは必ず `git_inspector.py` を呼び出すこと。
直接 `git log` や `git diff` は使わない。

### コマンド例

直近20件のコミットを見る:

```bash
python .claude/skills/git-inspect/git_inspector.py log -n 20 --json
```

コミット詳細を見る（hash は実際の値に置き換える）:

```bash
python .claude/skills/git-inspect/git_inspector.py show <hash> --json
```

差分を見る:

```bash
python .claude/skills/git-inspect/git_inspector.py diff main HEAD --json
```

### 出力の読み方

`--json` フラグで構造化 JSON が返るので、`hash`, `subject`, `diff` などのキーで目的の情報を取り出す。
