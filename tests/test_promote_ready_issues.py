from pathlib import Path
import subprocess

import pytest

from scripts import check_project_state as project_state
from scripts.promote_ready_issues import PromotionError, find_promotable, promote


def _item(
    item_id: str,
    status: str,
    *,
    depends_on: list[str] | None = None,
    owner: str | None = None,
    complete: bool = True,
) -> str:
    checkbox = "[x]" if status == "done" else ("[ ]" if complete else "not a checkbox")
    return f"""---
id: {item_id}
title: {item_id} test issue
status: {status}
priority: P1
type: quality
milestone: M4
depends_on: {depends_on or []}
touches:
  - src/example.py
owner: {owner if owner is not None else 'null'}
---

# {item_id}

## 背景と根本原因

根本原因

## 根拠

`src/example.py`

## 受け入れ条件

- {checkbox} criteria

## 対象外

対象外

## 実装計画

計画

## 完了証拠

証拠
"""


def _project(tmp_path: Path, *, candidate: str = "proposed", dependency: str = "done") -> Path:
    items_dir = tmp_path / "docs" / "project" / "items"
    items_dir.mkdir(parents=True)
    (items_dir / "SL-001-dependency.md").write_text(
        _item("SL-001", dependency, complete=dependency == "done"), encoding="utf-8"
    )
    (items_dir / "SL-002-candidate.md").write_text(
        _item("SL-002", candidate, depends_on=["SL-001"]), encoding="utf-8"
    )
    (tmp_path / "docs" / "project" / "roadmap.md").write_text(
        "# Roadmap\n\n## M4\n", encoding="utf-8"
    )
    items, issues = project_state.load_items(items_dir)
    assert not issues
    project_state.write_backlog(
        tmp_path / "docs" / "project" / "backlog.md",
        project_state.render_backlog(items),
    )
    return tmp_path


def test_check_is_read_only_and_finds_only_ready_contracts(tmp_path: Path):
    root = _project(tmp_path)
    candidate = root / "docs/project/items/SL-002-candidate.md"
    before = candidate.read_bytes()

    assert [item.id for item in find_promotable(root)] == ["SL-002"]
    assert candidate.read_bytes() == before


def test_promote_updates_item_renders_backlog_and_rechecks(tmp_path: Path):
    root = _project(tmp_path)

    assert promote(root, ["SL-002"], verify_git=False) == ("SL-002",)
    assert "status: ready" in (
        root / "docs/project/items/SL-002-candidate.md"
    ).read_text()
    assert "| [SL-002]" in (root / "docs/project/backlog.md").read_text()
    assert project_state.run("check", root) == 0


def test_promote_runs_state_update_render_and_check_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = _project(tmp_path)
    calls: list[str] = []
    original_run = project_state.run

    def recording_run(command: str, command_root: Path) -> int:
        calls.append(command)
        return original_run(command, command_root)

    monkeypatch.setattr(project_state, "run", recording_run)

    assert promote(root, ["SL-002"], verify_git=False) == ("SL-002",)
    assert calls == ["check", "render", "check"]


def test_failed_render_restores_all_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = _project(tmp_path)
    candidate = root / "docs/project/items/SL-002-candidate.md"
    backlog = root / "docs/project/backlog.md"
    before_candidate = candidate.read_bytes()
    before_backlog = backlog.read_bytes()
    original_run = project_state.run

    def fail_render(command: str, command_root: Path) -> int:
        if command == "render":
            return 1
        return original_run(command, command_root)

    monkeypatch.setattr(project_state, "run", fail_render)

    with pytest.raises(PromotionError, match="render"):
        promote(root, ["SL-002"], verify_git=False)
    assert candidate.read_bytes() == before_candidate
    assert backlog.read_bytes() == before_backlog


def test_process_skill_connects_only_normal_completion_to_handoff():
    process_skill = Path(".agents/skills/process-project-backlog/SKILL.md").read_text()
    handoff_skill = Path(
        ".agents/skills/promote-ready-project-issues/SKILL.md"
    ).read_text()

    assert "着手可能な課題なし" in process_skill
    assert "$promote-ready-project-issues" in process_skill
    assert "scripts/promote_ready_issues.py check" in handoff_skill
    assert "scripts/promote_ready_issues.py promote --ids" in handoff_skill


def test_dependency_not_done_is_not_promotable(tmp_path: Path):
    root = _project(tmp_path, dependency="proposed")

    assert find_promotable(root) == []


def test_incomplete_acceptance_is_not_promotable(tmp_path: Path):
    root = _project(tmp_path)
    candidate = root / "docs/project/items/SL-002-candidate.md"
    candidate.write_text(
        candidate.read_text().replace("- [ ] criteria", "not a checkbox"),
        encoding="utf-8",
    )
    items, issues = project_state.load_items(root / "docs/project/items")
    assert not issues
    project_state.write_backlog(
        root / "docs/project/backlog.md", project_state.render_backlog(items)
    )

    assert find_promotable(root) == []


def test_active_issue_blocks_promotion_without_writes(tmp_path: Path):
    root = _project(tmp_path)
    active = root / "docs/project/items/SL-003-active.md"
    active.write_text(_item("SL-003", "in_progress", owner="Codex"), encoding="utf-8")
    items, issues = project_state.load_items(root / "docs/project/items")
    assert not issues
    project_state.write_backlog(
        root / "docs/project/backlog.md", project_state.render_backlog(items)
    )
    candidate = root / "docs/project/items/SL-002-candidate.md"
    before = candidate.read_bytes()

    with pytest.raises(PromotionError, match="in_progress"):
        promote(root, ["SL-002"], verify_git=False)
    assert candidate.read_bytes() == before


def test_promote_requires_clean_main_before_writing(tmp_path: Path):
    root = _project(tmp_path)
    candidate = root / "docs/project/items/SL-002-candidate.md"
    before = candidate.read_bytes()

    with pytest.raises(PromotionError, match="clean な main"):
        promote(root, ["SL-002"])
    assert candidate.read_bytes() == before


def test_handoff_forward_path_commits_and_returns_to_clean_main(tmp_path: Path):
    root = _project(tmp_path)

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

    git("init", "-q")
    git("branch", "-M", "main")
    git("config", "user.name", "SheetLens Test")
    git("config", "user.email", "sheetlens-test@example.invalid")
    git("add", "docs/project/items/SL-001-dependency.md", "docs/project/items/SL-002-candidate.md", "docs/project/roadmap.md", "docs/project/backlog.md")
    git("commit", "-q", "-m", "test: seed project state")

    assert promote(root, ["SL-002"]) == ("SL-002",)
    git("add", "docs/project/items/SL-002-candidate.md", "docs/project/backlog.md")
    git("commit", "-q", "-m", "docs(project): promote eligible issues to ready")

    assert git("branch", "--show-current").stdout.strip() == "main"
    assert git("status", "--porcelain").stdout == ""
    assert project_state.run("check", root) == 0
