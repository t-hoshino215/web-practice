#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["ruff"]
# ///
"""
Claude Code PostToolUse Hook: ruff lint & format
=================================================
Pythonファイルの編集・作成後に ruff check --fix と ruff format を自動実行する。

使い方:
  .claude/settings.json に以下を追加:

  {
    "hooks": {
      "PostToolUse": [
        {
          "matcher": "Edit|MultiEdit|Write",
          "hooks": [
            {
              "type": "command",
              "command": "uv run \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/ruff-lint-format.py"
            }
          ]
        }
      ]
    }
  }
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def get_file_path_from_stdin() -> str | None:
    """stdin から Claude Code が渡す JSON を読み取り、ファイルパスを返す。"""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return None

    # Write ツールは "file_path"、Edit/MultiEdit も "file_path" を使う
    file_path = tool_input.get("file_path") or tool_input.get("path")
    if not isinstance(file_path, str):
        return None
    return file_path


def run_ruff(file_path: str) -> None:
    """ruff check --fix と ruff format を順に実行する。"""
    path = Path(file_path)

    if not path.exists():
        return

    # ruff check --fix: 自動修正可能なリントエラーを修正
    subprocess.run(
        ["ruff", "check", "--fix", str(path)],
        capture_output=True,
    )

    # ruff format: コードフォーマット
    subprocess.run(
        ["ruff", "format", str(path)],
        capture_output=True,
    )


def main() -> None:
    # stdin から Claude Code が渡す JSON を読み取り、ファイルパスを返す。
    file_path = get_file_path_from_stdin()

    # ファイルの存在確認
    if not file_path:
        sys.exit(0)

    # Python ファイル以外はスキップ
    if not file_path.endswith(".py"):
        sys.exit(0)

    try:
        # ruff 実行
        run_ruff(file_path)
    except FileNotFoundError:
        # ruff がインストールされていない場合はサイレントに終了
        # (exit code 2 は Claude Code がブロックと解釈するため避ける)
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
