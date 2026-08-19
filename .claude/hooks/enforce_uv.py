#!/usr/bin/env python3
"""
PreToolUse hook that blocks direct python/pip usage and suggests uv.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from typing import Any

SHELL_OPERATORS_RE = re.compile(r"\s*(?:&&|\|\||[;|])\s*")

PREFIX_COMMANDS = {"sudo", "command"}


def emit(decision: str, reason: str | None = None) -> None:
    """Emit a hook decision as JSON and terminate successfully.

    Args:
        decision (str): Hook decision to emit. Expected values are "approve" or
            "block".
        reason (str | None): Human-readable explanation for blocked commands.
            Omit when approving a command.

    Returns:
        None: This function does not return and exits the process with status 0.
    """
    payload: dict[str, str] = {"decision": decision}
    if reason is not None:
        payload["reason"] = reason
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(0)


def approve() -> None:
    """Emit an approval decision for the current hook invocation.

    Returns:
        None: This function does not return and exits the process with status 0.
    """
    emit("approve")


def block(reason: str) -> None:
    """Emit a blocking decision with an explanatory message.

    Args:
        reason (str): Message shown to the user explaining the uv alternative.

    Returns:
        None: This function does not return and exits the process with status 0.
    """
    emit("block", reason)


def read_payload() -> dict[str, Any] | None:
    """Read and validate the JSON payload from standard input.

    Returns:
        dict[str, Any] | None: Parsed payload when the input is valid JSON object;
            otherwise None.
    """
    raw = sys.stdin.read()
    if not raw.strip():
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None
    return data


def get_command(data: dict[str, Any]) -> str:
    """Extract the shell command string from the hook payload.

    Args:
        data (dict[str, Any]): Parsed PreToolUse hook payload.

    Returns:
        str: Normalized command string, or an empty string when unavailable.
    """
    tool_input: dict[str, Any] = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return ""

    command = tool_input.get("command", "")
    if not isinstance(command, str):
        return ""
    return command.strip()


def split_command(command: str) -> list[str]:
    """Split a shell command into tokens.

    Args:
        command (str): Raw shell command string.

    Returns:
        list[str]: Tokenized command. Falls back to whitespace splitting if
            shell-style parsing fails.
    """
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return command.split()


def split_shell_commands(command: str) -> list[str]:
    """Split a compound shell command on operators (&&, ||, ;, |).

    Args:
        command (str): Raw shell command string that may contain shell operators.

    Returns:
        list[str]: Individual sub-commands with surrounding whitespace removed.
            Empty segments are excluded.
    """
    parts = SHELL_OPERATORS_RE.split(command)
    return [part.strip() for part in parts if part.strip()]


def strip_prefix_commands(tokens: list[str]) -> list[str]:
    """Remove leading prefix commands (sudo, env, command) from token list.

    Args:
        tokens (list[str]): Tokenized command that may start with prefix commands.

    Returns:
        list[str]: Tokens with prefix commands stripped, exposing the real command.
    """
    index = 0
    while index < len(tokens):
        if tokens[index] in PREFIX_COMMANDS:
            index += 1
            continue
        if tokens[index] == "env":
            index += 1
            while index < len(tokens) and "=" in tokens[index]:
                index += 1
            continue
        break
    return tokens[index:]


def join_args(tokens: list[str]) -> str:
    """Join command tokens into a printable argument string.

    Args:
        tokens (list[str]): Command tokens to join.

    Returns:
        str: Tokens joined by a single space with surrounding whitespace removed.
    """
    return " ".join(tokens).strip()


def get_option_value(tokens: list[str], *names: str) -> str | None:
    """Find the value associated with one of the given CLI options.

    Args:
        tokens (list[str]): Tokenized command arguments to inspect.
        *names (str): Option names to match, such as "-r" or "--requirement".

    Returns:
        str | None: Option value when found, including `--name=value` form;
            otherwise None.
    """
    for index, token in enumerate(tokens):
        if token in names and index + 1 < len(tokens):
            return tokens[index + 1]

        for name in names:
            prefix = f"{name}="
            if token.startswith(prefix):
                return token[len(prefix) :]

    return None


def filter_install_targets(tokens: list[str]) -> list[str]:
    """Remove install-only flags so package targets can be suggested cleanly.

    Args:
        tokens (list[str]): Arguments passed to `pip install`.

    Returns:
        list[str]: Remaining package targets with handled flags removed.
    """
    filtered: list[str] = []
    skip_next = False

    for token in tokens:
        if skip_next:
            skip_next = False
            continue

        if token in {"-r", "--requirement", "-c", "--constraint", "-e", "--editable", "--dev"}:
            skip_next = token in {"-r", "--requirement", "-c", "--constraint", "-e", "--editable"}
            continue

        if token.startswith("--requirement=") or token.startswith("--constraint=") or token.startswith("--editable="):
            continue

        filtered.append(token)

    return filtered


def handle_pip(tokens: list[str]) -> None:
    """Block direct pip usage and suggest the equivalent uv command.

    Args:
        tokens (list[str]): Tokenized pip or pip3 command.

    Returns:
        None: This function does not return and emits a hook decision.
    """
    if len(tokens) < 2:
        block("pip の代わりに uv pip または uv add/remove を使ってください。")
        return  # unreachable but guards against future refactoring

    subcommand = tokens[1]

    if subcommand == "install":
        install_args = tokens[2:]
        requirement_file = get_option_value(install_args, "-r", "--requirement")
        if requirement_file:
            constraint_file = get_option_value(install_args, "-c", "--constraint")
            example = f"uv add -r {requirement_file}"
            if constraint_file:
                example = f"{example} -c {constraint_file}"
            block(f"requirements ファイルからのインストールには uv add -r を使ってください。\n\n例: {example}")
            return

        editable_target = get_option_value(install_args, "-e", "--editable")
        if editable_target:
            block(f"編集可能インストールには uv add -e を使ってください。\n\n例: uv add -e {editable_target}")
            return

        packages = join_args(filter_install_targets(install_args))
        if "--dev" in install_args:
            if packages:
                block(f"開発依存関係の追加には uv add --dev を使ってください。\n\n例: uv add --dev {packages}")
                return
            block("開発依存関係の追加には uv add --dev を使ってください。")
            return

        if packages:
            block(f"パッケージのインストールには uv add を使ってください。\n\n例: uv add {packages}")
            return
        block("パッケージのインストールには uv add を使ってください。")
        return

    if subcommand == "uninstall":
        packages = join_args([token for token in tokens[2:] if token != "-y"])
        if packages:
            block(f"パッケージの削除には uv remove を使ってください。\n\n例: uv remove {packages}")
            return
        block("パッケージの削除には uv remove を使ってください。")
        return

    if subcommand in {"list", "freeze"}:
        block(
            "依存関係の確認には uv 側のコマンドを使ってください。\n\n"
            "例:\n"
            "- uv tree\n"
            "- uv export --format requirements-txt"
        )
        return

    args = join_args(tokens[1:])
    block(f"pip の代わりに uv を使ってください。\n\n例: uv {args}")


def handle_python(tokens: list[str]) -> None:
    """Block direct Python execution and suggest the uv-based alternative.

    Args:
        tokens (list[str]): Tokenized python, python3, or py command.

    Returns:
        None: This function does not return and emits a hook decision.
    """
    executable = tokens[0]
    args = tokens[1:]

    if not args:
        block(f"{executable} の代わりに uv 経由で実行してください。\n\n例: uv run python")
        return

    if args[0] == "-m":
        if len(args) >= 2 and args[1] == "pip":
            handle_pip(["pip", *args[2:]])
            return

        if len(args) >= 2 and args[1] in {"pytest", "ruff"}:
            handle_uv_run_tool([args[1], *args[2:]])
            return

        module_args = join_args(args)
        block(f"モジュール実行は uv 経由で行ってください。\n\n例: uv run python {module_args}")
        return

    joined_args = join_args(args)
    block(f"Python 実行は uv 経由で行ってください。\n\n例: uv run python {joined_args}")


def handle_uv_run_tool(tokens: list[str]) -> None:
    """Suggest running supported tools through `uv run`.

    Args:
        tokens (list[str]): Tokenized command for tools such as pytest or ruff.

    Returns:
        None: This function does not return and emits a hook decision.
    """
    tool_name = tokens[0]
    args = join_args(tokens[1:])
    if args:
        block(f"{tool_name} は uv 経由で実行してください。\n\n例: uv run {tool_name} {args}")
        return
    block(f"{tool_name} は uv 経由で実行してください。\n\n例: uv run {tool_name}")


def check_tokens(tokens: list[str]) -> None:
    """Check a single sub-command's tokens and block if forbidden.

    Args:
        tokens (list[str]): Tokenized sub-command with prefixes already stripped.

    Returns:
        None: Calls block() if the command is forbidden, otherwise returns normally.
    """
    if not tokens:
        return

    head = tokens[0]
    if head in {"pip", "pip3"}:
        handle_pip(tokens)
    elif head in {"python", "python3", "py"}:
        handle_python(tokens)
    elif head in {"pytest", "ruff"}:
        handle_uv_run_tool(tokens)


def main() -> None:
    """Process a PreToolUse hook payload and emit the appropriate decision.

    Returns:
        None: This function does not return and always emits a hook decision.
    """
    data = read_payload()
    if data is None:
        approve()
        return

    if data.get("tool_name") != "Bash":
        approve()
        return

    command = get_command(data)
    if not command:
        approve()
        return

    sub_commands = split_shell_commands(command)

    for sub_command in sub_commands:
        if sub_command.startswith("uv "):
            continue

        tokens = split_command(sub_command)
        if not tokens:
            continue

        tokens = strip_prefix_commands(tokens)
        check_tokens(tokens)

    approve()


if __name__ == "__main__":
    main()
