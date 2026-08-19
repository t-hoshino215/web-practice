"""Git history inspection script.

直近の実装や変更を調査するための CLI ツール。
log / show / diff の 3 サブコマンドを提供し、人間向けテキスト出力と
機械可読な JSON 出力の両方をサポートする。

Examples:
    $ python git_inspector.py log -n 5
    $ python git_inspector.py log --since="2 weeks ago" --json
    $ python git_inspector.py show HEAD --json
    $ python git_inspector.py diff main HEAD --path src/
"""

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# git log のフィールド区切り。コミットメッセージに混入しにくい
# ASCII Unit Separator (0x1F) を使い、split のあいまい性を排除する。
_FIELD_SEP: str = "\x1f"


class GitCommandError(RuntimeError):
    """git サブコマンドが非ゼロ終了したときに送出される例外."""


@dataclass(frozen=True, slots=True)
class CommitSummary:
    """単一コミットのサマリ情報.

    Attributes:
        hash: フルコミットハッシュ (SHA-1).
        short_hash: 短縮ハッシュ.
        author: 作者名とメールアドレス ("Name <email>" 形式).
        date: ISO 8601 形式のコミット日時.
        subject: コミットメッセージの 1 行目.
    """

    hash: str
    short_hash: str
    author: str
    date: str
    subject: str


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    """git コマンドを実行して標準出力を返す.

    Args:
        args: ``git`` 自体を除いた引数リスト (例: ``["log", "-n5"]``).
        cwd: 実行するリポジトリのパス. None なら現在のディレクトリ.

    Returns:
        コマンドの標準出力 (UTF-8 デコード済み).

    Raises:
        GitCommandError: git が非ゼロで終了したとき.
    """
    # Popen ではなく run を使うのは、待ち合わせ・エラー処理がシンプルになるため。
    # errors="replace" は、稀に混入する非 UTF-8 バイトでクラッシュさせないための保険。
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise GitCommandError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _parse_log_line(line: str, sep: str = _FIELD_SEP) -> CommitSummary:
    """``git log --pretty=format:...`` の 1 行をパースする.

    Args:
        line: 出力 1 行分の文字列.
        sep: フォーマット指定で使ったフィールド区切り文字.

    Returns:
        パース済みの :class:`CommitSummary`.
    """
    # subject にも sep と異なる任意文字が含まれうるため、split は maxsplit=4 で固定する。
    full_hash, short_hash, author, date, subject = line.split(sep, 4)
    return CommitSummary(
        hash=full_hash,
        short_hash=short_hash,
        author=author,
        date=date,
        subject=subject,
    )


def get_log(
    limit: int = 20,
    path: str | None = None,
    author: str | None = None,
    since: str | None = None,
    repo: Path | None = None,
) -> list[CommitSummary]:
    """直近のコミットを構造化サマリとして取得する.

    Args:
        limit: 取得する最大コミット数.
        path: 指定するとそのパスに触れたコミットだけに絞る.
        author: 作者名による絞り込み (部分一致).
        since: 日付フィルタ (例: ``"2 weeks ago"``, ``"2025-01-01"``).
        repo: リポジトリのパス. None なら現在のディレクトリ.

    Returns:
        新しい順に並んだ :class:`CommitSummary` のリスト.
    """
    # %H=full hash, %h=short, %an<%ae>=author, %aI=ISO date, %s=subject
    fmt = _FIELD_SEP.join(["%H", "%h", "%an <%ae>", "%aI", "%s"])
    args = ["log", f"--pretty=format:{fmt}", f"-n{limit}"]

    # 条件付き引数は順序が重要 (--path は最後の "--" の後)。
    if author:
        args.append(f"--author={author}")
    if since:
        args.append(f"--since={since}")
    if path:
        args.extend(["--", path])

    output = _run_git(args, cwd=repo)
    return [_parse_log_line(line) for line in output.splitlines() if line.strip()]


def get_commit_detail(commit: str, repo: Path | None = None) -> dict[str, Any]:
    """単一コミットの詳細情報を取得する.

    メタ情報・変更ファイル統計・フル diff をまとめて返す.
    Claude Code が「このコミットで何が起きたか」を 1 回の呼び出しで把握できるように構成。

    Args:
        commit: コミットハッシュまたはリファレンス (例: ``"HEAD"``, ``"abc123"``).
        repo: リポジトリのパス.

    Returns:
        メタ情報・統計・diff を含む辞書.
    """
    # メタ情報と diff は別コマンドで取る。1 コマンドで取ろうとすると
    # 改行を含む body と diff の境界判定が複雑になるため。
    fmt = _FIELD_SEP.join(["%H", "%h", "%an <%ae>", "%aI", "%s", "%b"])
    meta_raw = _run_git(["show", "-s", f"--pretty=format:{fmt}", commit], cwd=repo)
    full_hash, short_hash, author, date, subject, body = meta_raw.split(_FIELD_SEP, 5)

    stats = _run_git(["show", "--stat", "--format=", commit], cwd=repo).strip()
    diff = _run_git(["show", "--format=", commit], cwd=repo)

    return {
        "hash": full_hash,
        "short_hash": short_hash,
        "author": author,
        "date": date,
        "subject": subject,
        "body": body,
        "stats": stats,
        "diff": diff,
    }


def get_diff(
    from_ref: str,
    to_ref: str = "HEAD",
    path: str | None = None,
    repo: Path | None = None,
) -> str:
    """2 つのリファレンス間の diff を取得する.

    Args:
        from_ref: 比較元のリファレンス (例: ``"main"``, ``"HEAD~5"``).
        to_ref: 比較先のリファレンス. デフォルトは ``"HEAD"``.
        path: 指定するとそのパスに対する diff だけを返す.
        repo: リポジトリのパス.

    Returns:
        ユニファイド形式の diff テキスト.
    """
    args = ["diff", f"{from_ref}..{to_ref}"]
    if path:
        args.extend(["--", path])
    return _run_git(args, cwd=repo)


def _build_parser() -> argparse.ArgumentParser:
    """CLI 用 ArgumentParser を組み立てる.

    Returns:
        サブコマンドを設定済みの :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(description="Inspect git history for Claude Code investigation.")
    parser.add_argument("--repo", type=Path, default=None, help="Path to git repository.")
    parser.add_argument("--json", action="store_true", help="Output as JSON.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_log = sub.add_parser("log", help="Show recent commits.")
    p_log.add_argument("-n", "--limit", type=int, default=20)
    p_log.add_argument("--path", default=None)
    p_log.add_argument("--author", default=None)
    p_log.add_argument("--since", default=None)

    p_show = sub.add_parser("show", help="Show details of a single commit.")
    p_show.add_argument("commit")

    p_diff = sub.add_parser("diff", help="Show diff between two refs.")
    p_diff.add_argument("from_ref")
    p_diff.add_argument("to_ref", nargs="?", default="HEAD")
    p_diff.add_argument("--path", default=None)

    return parser


def _print_log(commits: list[CommitSummary], as_json: bool) -> None:
    """log サブコマンドの結果を標準出力に書き出す."""
    if as_json:
        print(json.dumps([asdict(c) for c in commits], ensure_ascii=False, indent=2))
        return
    for c in commits:
        print(f"{c.short_hash}  {c.date}  {c.author}\n    {c.subject}")


def _print_detail(detail: dict[str, Any], as_json: bool) -> None:
    """show サブコマンドの結果を標準出力に書き出す."""
    if as_json:
        print(json.dumps(detail, ensure_ascii=False, indent=2))
        return
    print(f"commit {detail['hash']}")
    print(f"Author: {detail['author']}")
    print(f"Date:   {detail['date']}\n")
    print(f"    {detail['subject']}\n")
    if detail["body"].strip():
        print(detail["body"])
    print("\n--- stats ---")
    print(detail["stats"])
    print("\n--- diff ---")
    print(detail["diff"])


def main(argv: list[str] | None = None) -> int:
    """CLI のエントリポイント.

    Args:
        argv: 引数リスト. None なら ``sys.argv[1:]`` が使われる.

    Returns:
        プロセス終了コード (0 = 成功, 1 = git エラー).
    """
    args = _build_parser().parse_args(argv)

    try:
        # match 文でサブコマンドごとに分岐 (Python 3.10+ の構造的パターンマッチ)
        match args.command:
            case "log":
                _print_log(
                    get_log(
                        limit=args.limit,
                        path=args.path,
                        author=args.author,
                        since=args.since,
                        repo=args.repo,
                    ),
                    as_json=args.json,
                )
            case "show":
                _print_detail(
                    get_commit_detail(args.commit, repo=args.repo),
                    as_json=args.json,
                )
            case "diff":
                print(
                    get_diff(
                        from_ref=args.from_ref,
                        to_ref=args.to_ref,
                        path=args.path,
                        repo=args.repo,
                    )
                )
    except GitCommandError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
