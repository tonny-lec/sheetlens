import importlib.util
import subprocess
from pathlib import Path


HOOK_PATH = Path(__file__).parents[1] / ".codex" / "hooks" / "stop_git_completion.py"
SPEC = importlib.util.spec_from_file_location("stop_git_completion", HOOK_PATH)
assert SPEC is not None and SPEC.loader is not None
hook = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hook)


def test_non_completion_message_does_not_run_checker(tmp_path):
    def unexpected_checker(_cwd):
        raise AssertionError("checker must not run")

    decision = hook.evaluate_stop(
        {"last_assistant_message": "調査結果を報告します。"},
        tmp_path,
        unexpected_checker,
    )

    assert decision is None


def test_completion_claim_is_blocked_with_actionable_reasons(tmp_path):
    decision = hook.evaluate_stop(
        {"last_assistant_message": "実装完了\n課題: SL-018"},
        tmp_path,
        lambda _cwd: ["現在のbranchがmainではありません", "未コミット変更があります"],
    )

    assert decision == {
        "decision": "block",
        "reason": (
            "実装完了を宣言する前に $finish-project-issue を完了してください: "
            "現在のbranchがmainではありません; 未コミット変更があります"
        ),
    }


def test_stop_hook_active_is_loop_safe(tmp_path):
    def unexpected_checker(_cwd):
        raise AssertionError("checker must not run on the continuation stop")

    decision = hook.evaluate_stop(
        {
            "stop_hook_active": True,
            "last_assistant_message": "実装完了\n課題: SL-018",
        },
        tmp_path,
        unexpected_checker,
    )

    assert decision is None


def test_clean_main_with_valid_project_state_allows_completion(tmp_path):
    decision = hook.evaluate_stop(
        {"last_assistant_message": "Implementation complete\nIssue: SL-018"},
        tmp_path,
        lambda _cwd: [],
    )

    assert decision is None


def test_completion_problems_report_branch_status_project_and_active_issue(tmp_path):
    root = tmp_path / "repo"
    backlog = root / "docs" / "project" / "backlog.md"
    backlog.parent.mkdir(parents=True)
    backlog.write_text(
        "| SL-018 | P1 | in_progress | M4 | Git | — | Codex |\n",
        encoding="utf-8",
    )

    def runner(command, _cwd):
        command = tuple(command)
        if command == ("git", "rev-parse", "--show-toplevel"):
            return 0, f"{root}\n", ""
        if command == ("git", "branch", "--show-current"):
            return 0, "feat/sl-018\n", ""
        if command == ("git", "status", "--porcelain"):
            return 0, " M AGENTS.md\n", ""
        if command[1:] == ("scripts/check_project_state.py", "check"):
            return 1, "backlog mismatch\n", ""
        raise AssertionError(command)

    problems = hook.completion_problems(root, runner)

    assert problems == [
        "現在のbranchがmainではありません（task branchのdoneは未統合の候補状態です）: feat/sl-018"
    ]


def test_clean_task_branch_with_provisional_done_is_blocked(tmp_path):
    root = tmp_path / "repo"
    backlog = root / "docs" / "project" / "backlog.md"
    backlog.parent.mkdir(parents=True)
    backlog.write_text(
        "| SL-020 | P1 | done | M4 | 完了状態 | — | — |\n",
        encoding="utf-8",
    )
    calls = []

    def runner(command, _cwd):
        command = tuple(command)
        calls.append(command)
        if command == ("git", "rev-parse", "--show-toplevel"):
            return 0, f"{root}\n", ""
        if command == ("git", "branch", "--show-current"):
            return 0, "feat/SL-020-completion-state-authority\n", ""
        if command == ("git", "status", "--porcelain"):
            return 0, "", ""
        if command[1:] == ("scripts/check_project_state.py", "check"):
            return 0, "", ""
        raise AssertionError(command)

    problems = hook.completion_problems(root, runner)

    assert problems == [
        "現在のbranchがmainではありません（task branchのdoneは未統合の候補状態です）: "
        "feat/SL-020-completion-state-authority",
    ]
    assert len(calls) == 2
    assert len(calls) < 4  # pre-SL-020 failure-path baseline


def test_unmerged_task_branch_is_forward_merged_before_selection(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args):
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout

    git("init", "-b", "main")
    git("config", "user.name", "SheetLens Test")
    git("config", "user.email", "sheetlens-test@example.invalid")
    backlog = root / "docs" / "project" / "backlog.md"
    backlog.parent.mkdir(parents=True)
    backlog.write_text("| SL-020 | P1 | ready | M4 | 完了状態 | — | — |\n", encoding="utf-8")
    git("add", "docs/project/backlog.md")
    git("commit", "-m", "seed")
    git("switch", "-c", "feat/SL-020-completion-state-authority")
    backlog.write_text("| SL-020 | P1 | done | M4 | 完了状態 | — | — |\n", encoding="utf-8")
    git("add", "docs/project/backlog.md")
    git("commit", "-m", "provisional done")
    git("switch", "main")

    unmerged = git("branch", "--no-merged", "main", "feat/SL-*")
    process_skill = (Path(__file__).parents[1] / ".agents/skills/process-project-backlog/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "feat/SL-020-completion-state-authority" in unmerged
    assert "do not invoke selection or start another issue" in process_skill

    git("merge", "--ff-only", "feat/SL-020-completion-state-authority")

    assert "done" in backlog.read_text(encoding="utf-8")
    assert git("branch", "--no-merged", "main", "feat/SL-*").strip() == ""


def test_completion_checker_proxy_metrics_are_bounded(tmp_path):
    root = tmp_path / "repo"
    backlog = root / "docs" / "project" / "backlog.md"
    backlog.parent.mkdir(parents=True)
    backlog.write_text("| SL-020 | P1 | ready | M4 | 完了状態 | — | — |\n", encoding="utf-8")
    calls = []
    output_bytes = 0

    def runner(command, _cwd):
        nonlocal output_bytes
        command = tuple(command)
        calls.append(command)
        if command == ("git", "rev-parse", "--show-toplevel"):
            stdout, stderr = f"{root}\n", ""
        elif command == ("git", "branch", "--show-current"):
            stdout, stderr = "main\n", ""
        elif command == ("git", "status", "--porcelain"):
            stdout, stderr = "", ""
        elif command[1:] == ("scripts/check_project_state.py", "check"):
            stdout, stderr = "", ""
        else:
            raise AssertionError(command)
        output_bytes += len(stdout.encode()) + len(stderr.encode())
        if command == ("git", "rev-parse", "--show-toplevel"):
            return 0, stdout, stderr
        if command == ("git", "branch", "--show-current"):
            return 0, stdout, stderr
        if command == ("git", "status", "--porcelain"):
            return 0, stdout, stderr
        if command[1:] == ("scripts/check_project_state.py", "check"):
            return 0, stdout, stderr

    assert hook.completion_problems(root, runner) == []
    baseline = {
        "commands": 4,
        "duplicates": 0,
        "output_bytes": len(f"{root}\nmain\n".encode()),
    }
    current = {
        "commands": len(calls),
        "duplicates": len(calls) - len(set(calls)),
        "output_bytes": output_bytes,
    }
    assert current == baseline
