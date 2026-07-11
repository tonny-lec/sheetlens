import importlib.util
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
        "現在のbranchがmainではありません: feat/sl-018",
        "作業ツリーに未コミット変更があります",
        "project-state checkが失敗しています: backlog mismatch",
        "in_progressの課題が残っています",
    ]
