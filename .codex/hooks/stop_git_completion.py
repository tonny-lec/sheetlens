#!/usr/bin/env python3
"""Block completion claims until the authoritative local Git state is complete.

The hook can verify the observable main/clean/project-state/active-issue boundary; it
cannot prove that the finish skill itself was followed or that tests were run.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

CommandRunner = Callable[[Sequence[str], Path], tuple[int, str, str]]
_COMPLETION_CLAIM = re.compile(
    r"(?:^|\n)(?:実装完了|Implementation complete)(?:\s|$)",
    re.IGNORECASE,
)


def claims_implementation_complete(message: object) -> bool:
    return isinstance(message, str) and _COMPLETION_CLAIM.search(message) is not None


def run_command(command: Sequence[str], cwd: Path) -> tuple[int, str, str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stdout, completed.stderr


def completion_problems(cwd: Path, runner: CommandRunner = run_command) -> list[str]:
    problems: list[str] = []
    code, root_text, error = runner(("git", "rev-parse", "--show-toplevel"), cwd)
    if code != 0:
        return [f"Git rootを確認できません: {error.strip() or root_text.strip()}"]
    root = Path(root_text.strip())

    code, branch, error = runner(("git", "branch", "--show-current"), root)
    if code != 0:
        problems.append(f"現在のbranchを確認できません: {error.strip()}")
    elif branch.strip() != "main":
        problems.append(
            "現在のbranchがmainではありません（task branchのdoneは未統合の候補状態です）: "
            f"{branch.strip() or 'detached HEAD'}"
        )
        return problems

    code, status, error = runner(("git", "status", "--porcelain"), root)
    if code != 0:
        problems.append(f"作業ツリーを確認できません: {error.strip()}")
    elif status.strip():
        problems.append("作業ツリーに未コミット変更があります")
        return problems

    project_check = (
        sys.executable,
        "scripts/check_project_state.py",
        "check",
    )
    code, output, error = runner(project_check, root)
    if code != 0:
        detail = (output + error).strip()
        problems.append(f"project-state checkが失敗しています: {detail}")

    backlog = root / "docs" / "project" / "backlog.md"
    try:
        backlog_text = backlog.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        problems.append(f"backlogを確認できません: {exc}")
    else:
        if re.search(r"\|\s*in_progress\s*\|", backlog_text):
            problems.append("in_progressの課題が残っています")
    return problems


def evaluate_stop(
    payload: object,
    cwd: Path,
    checker: Callable[[Path], list[str]] = completion_problems,
) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("stop_hook_active") is True:
        return None
    if not claims_implementation_complete(payload.get("last_assistant_message")):
        return None
    problems = checker(cwd)
    if not problems:
        return None
    return {
        "decision": "block",
        "reason": (
            "実装完了を宣言する前に $finish-project-issue を完了してください: "
            + "; ".join(problems)
        ),
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    decision = evaluate_stop(payload, Path.cwd())
    if decision is not None:
        print(json.dumps(decision, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
