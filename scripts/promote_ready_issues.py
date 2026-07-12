from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_project_state as project_state  # noqa: E402


_FRONT_MATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---(?:\r?\n|$)", re.S)
_STATUS_RE = re.compile(r"^status: proposed$", re.M)
_READY_SECTIONS = ("背景と根本原因", "根拠", "受け入れ条件", "対象外")


class PromotionError(RuntimeError):
    pass


def _validated_items(root: Path) -> list[project_state.ProjectItem]:
    if project_state.run("check", root) != 0:
        raise PromotionError("project-state check に失敗したため ready 昇格を中止しました")
    items, issues = project_state.load_items(root / "docs" / "project" / "items")
    if issues:
        raise PromotionError("課題ファイルの再読込に失敗したため ready 昇格を中止しました")
    active = sorted(item.id for item in items if item.status == "in_progress")
    if active:
        raise PromotionError(
            "in_progress の課題が残っているため ready 昇格を中止しました: "
            + ", ".join(active)
        )
    return items


def _is_promotable(
    item: project_state.ProjectItem,
    by_id: dict[str, project_state.ProjectItem],
) -> bool:
    if item.status != "proposed" or not item.touches:
        return False
    if not all(
        project_state.validation_section_text(item, name).strip()
        for name in _READY_SECTIONS
    ):
        return False
    acceptance = project_state.validation_section_text(item, "受け入れ条件")
    if not project_state.acceptance_criteria_structure_valid(acceptance):
        return False
    return all(dep in by_id and by_id[dep].status == "done" for dep in item.depends_on)


def find_promotable(root: Path) -> list[project_state.ProjectItem]:
    items = _validated_items(root)
    by_id = {item.id: item for item in items}
    return sorted(
        (item for item in items if _is_promotable(item, by_id)),
        key=lambda item: (project_state.PRIORITY_ORDER[item.priority], item.milestone, item.id),
    )


def _write_atomic(path: Path, text: str) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _promote_item(item: project_state.ProjectItem) -> None:
    text = item.path.read_text(encoding="utf-8")
    front_matter = _FRONT_MATTER_RE.match(text)
    if front_matter is None:
        raise PromotionError(f"front matter を再解析できません: {item.path}")
    updated_front_matter, count = _STATUS_RE.subn("status: ready", front_matter.group(0), count=1)
    if count != 1:
        raise PromotionError(f"status: proposed を更新できません: {item.path}")
    _write_atomic(item.path, updated_front_matter + text[front_matter.end() :])


def _assert_clean_main(root: Path) -> None:
    try:
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            check=False,
            capture_output=True,
            text=True,
        )
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise PromotionError(f"Git 状態を確認できません: {exc}") from exc
    if branch.returncode != 0 or branch.stdout.strip() != "main":
        raise PromotionError("ready 昇格は clean な main でのみ実行できます")
    if status.returncode != 0:
        raise PromotionError("Git の作業ツリー状態を確認できません")
    if status.stdout:
        raise PromotionError("作業ツリーが clean ではないため ready 昇格を中止しました")


def _restore(path: Path, original: bytes | None) -> None:
    if original is None:
        path.unlink(missing_ok=True)
    else:
        path.write_bytes(original)


def promote(
    root: Path,
    issue_ids: Sequence[str],
    *,
    verify_git: bool = True,
) -> tuple[str, ...]:
    if verify_git:
        _assert_clean_main(root)
    candidates = find_promotable(root)
    requested = tuple(issue_ids)
    if len(set(requested)) != len(requested):
        raise PromotionError("昇格対象 ID が重複しています")
    candidates_by_id = {item.id: item for item in candidates}
    unknown = tuple(issue_id for issue_id in requested if issue_id not in candidates_by_id)
    if unknown:
        raise PromotionError(
            "昇格条件を満たさない ID が指定されました: " + ", ".join(unknown)
        )
    selected = [candidates_by_id[issue_id] for issue_id in requested]
    if not selected:
        return ()

    backlog = root / "docs" / "project" / "backlog.md"
    originals = {item.path: item.path.read_bytes() for item in selected}
    originals[backlog] = backlog.read_bytes()
    try:
        for item in selected:
            _promote_item(item)
        if project_state.run("render", root) != 0:
            raise PromotionError("ready 昇格後の backlog render に失敗しました")
        if project_state.run("check", root) != 0:
            raise PromotionError("ready 昇格後の project-state check に失敗しました")
    except BaseException:
        try:
            for path, original in originals.items():
                _restore(path, original)
        except OSError as rollback_exc:
            raise PromotionError(
                "ready 昇格の失敗後に状態を復元できませんでした"
            ) from rollback_exc
        raise
    return requested


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="proposed 課題を ready 条件に従って昇格する")
    parser.add_argument("command", choices=("check", "promote"))
    parser.add_argument("--ids", nargs="*", default=(), help="check で確認した昇格対象 ID")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "promote":
            promoted = promote(root, args.ids)
            print("readyへ変更: " + (", ".join(promoted) if promoted else "なし"))
        else:
            candidates = find_promotable(root)
            print("ready候補: " + (", ".join(item.id for item in candidates) if candidates else "なし"))
    except (OSError, PromotionError) as exc:
        print(f"ready昇格エラー: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
