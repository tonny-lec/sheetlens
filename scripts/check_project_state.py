from __future__ import annotations

import argparse
import errno
import os
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

import yaml

ALLOWED_KEYS = {
    "id",
    "title",
    "status",
    "priority",
    "type",
    "milestone",
    "depends_on",
    "touches",
    "owner",
}
VALID_STATUS = {"proposed", "ready", "in_progress", "blocked", "done", "cancelled"}
VALID_PRIORITY = {"P0", "P1", "P2", "P3"}
VALID_TYPE = {"defect", "refactor", "enhancement", "quality"}
VALID_MILESTONE = {"M1", "M2", "M3", "M4"}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
ID_RE = re.compile(r"SL-\d{3}\Z")
FRONT_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.S)
FENCE_OPEN_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})[^\r\n]*$")
SECTION_HEADING_RE = re.compile(r"^## ([^\n]+)\r?\n", re.M)
LIST_ITEM_RE = re.compile(
    r"^[ \t]*(?:[-+*]|\d{1,9}[.)])(?P<rest>(?:[ \t]+[^\r\n]*)?)\r?$",
    re.M,
)
TASK_CHECKBOX_RE = re.compile(r"^\[([ xX])\][ \t]+\S.*$")
MILESTONE_RE = re.compile(r"^## (M[1-4])(?:\s|$)", re.M)


class _DuplicateMappingKeyError(yaml.YAMLError):
    pass


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise _DuplicateMappingKeyError(
                f"mapping キーが重複しています: {key!r}"
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True)
class ProjectIssue:
    path: Path
    message: str


@dataclass(frozen=True)
class ProjectItem:
    path: Path
    id: str
    title: str
    status: str
    priority: str
    type: str
    milestone: str
    depends_on: tuple[str, ...]
    touches: tuple[str, ...]
    owner: str | None
    body: str


def _issue(path: Path, message: str) -> ProjectIssue:
    return ProjectIssue(path=path, message=message)


def _front_matter_key_sort_key(key: object) -> tuple[int, str, str]:
    if isinstance(key, str):
        return 0, "", key
    return 1, type(key).__name__, repr(key)


def _touch_path_is_canonical(value: str) -> bool:
    if value == ".":
        return True
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or PureWindowsPath(value).drive
    ):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def parse_item(path: Path) -> tuple[ProjectItem | None, list[ProjectIssue]]:
    text = path.read_text(encoding="utf-8")
    match = FRONT_RE.match(text)
    if not match:
        return None, [_issue(path, "YAML front matter を解析できません")]
    try:
        raw = yaml.load(match.group(1), Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as exc:
        return None, [_issue(path, f"YAML front matter が不正です: {exc}")]
    if not isinstance(raw, dict):
        return None, [_issue(path, "front matter は mapping で記述してください")]

    unknown_keys = sorted(set(raw) - ALLOWED_KEYS, key=_front_matter_key_sort_key)
    issues = []
    for key in unknown_keys:
        if isinstance(key, str):
            issues.append(_issue(path, f"未知の front matter キーです: {key}"))
        else:
            issues.append(_issue(path, f"front matter キーは文字列で指定してください: {key!r}"))
    required = ALLOWED_KEYS
    issues.extend(
        _issue(path, f"必須キーがありません: {key}")
        for key in sorted(required - set(raw))
    )

    item_id = raw.get("id")
    if isinstance(item_id, str) and not path.name.startswith(f"{item_id}-"):
        issues.append(_issue(path, f"ファイル名は {item_id}- で始めてください"))
    if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
        issues.append(_issue(path, "id は SL-001 形式で指定してください"))

    scalar_rules = {
        "title": str,
        "status": str,
        "priority": str,
        "type": str,
        "milestone": str,
    }
    for key, expected in scalar_rules.items():
        if key in raw and not isinstance(raw[key], expected):
            issues.append(_issue(path, f"{key} の型が不正です"))
    for key in ("depends_on", "touches"):
        if key in raw and (
            not isinstance(raw[key], list)
            or not all(isinstance(value, str) for value in raw[key])
        ):
            issues.append(_issue(path, f"{key} は文字列の配列で指定してください"))
    touches = raw.get("touches")
    if isinstance(touches, list) and all(isinstance(value, str) for value in touches):
        issues.extend(
            _issue(path, f"touches の path が不正です: {value!r}")
            for value in touches
            if not _touch_path_is_canonical(value)
        )
    if raw.get("owner") is not None and not isinstance(raw.get("owner"), str):
        issues.append(_issue(path, "owner は文字列または null で指定してください"))
    if isinstance(raw.get("status"), str) and raw["status"] not in VALID_STATUS:
        issues.append(_issue(path, f"不正な status です: {raw['status']}"))
    if isinstance(raw.get("priority"), str) and raw["priority"] not in VALID_PRIORITY:
        issues.append(_issue(path, f"不正な priority です: {raw['priority']}"))
    if isinstance(raw.get("type"), str) and raw["type"] not in VALID_TYPE:
        issues.append(_issue(path, f"不正な type です: {raw['type']}"))
    if isinstance(raw.get("milestone"), str) and raw["milestone"] not in VALID_MILESTONE:
        issues.append(_issue(path, f"不正な milestone です: {raw['milestone']}"))
    if issues:
        return None, issues

    return ProjectItem(
        path=path,
        id=raw["id"],
        title=raw["title"],
        status=raw["status"],
        priority=raw["priority"],
        type=raw["type"],
        milestone=raw["milestone"],
        depends_on=tuple(raw["depends_on"]),
        touches=tuple(raw["touches"]),
        owner=raw["owner"],
        body=match.group(2),
    ), []


def load_items(items_dir: Path) -> tuple[list[ProjectItem], list[ProjectIssue]]:
    items: list[ProjectItem] = []
    issues: list[ProjectIssue] = []
    for path in sorted(items_dir.glob("*.md")):
        try:
            item, item_issues = parse_item(path)
        except (OSError, UnicodeError) as exc:
            issues.append(_issue(path, f"課題ファイルを読めません: {exc}"))
            continue
        issues.extend(item_issues)
        if item is not None:
            items.append(item)
    return items, issues


def _mask_fenced_blocks(text: str) -> str:
    masked_lines: list[str] = []
    fence_char: str | None = None
    fence_length = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        if fence_char is None:
            match = FENCE_OPEN_RE.fullmatch(content)
            if match:
                fence = match.group("fence")
                fence_char = fence[0]
                fence_length = len(fence)
        else:
            candidate = content.lstrip(" ")
            indent = len(content) - len(candidate)
            run_length = len(candidate) - len(candidate.lstrip(fence_char))
            if (
                indent <= 3
                and run_length >= fence_length
                and not candidate[run_length:].strip(" \t")
            ):
                fence_char = None
                fence_length = 0
        if fence_char is not None or FENCE_OPEN_RE.fullmatch(content):
            masked_lines.append(
                "".join(character if character in "\r\n" else " " for character in line)
            )
        else:
            masked_lines.append(line)
    return "".join(masked_lines)


def _sections(text: str) -> list[tuple[str, str]]:
    headings = list(SECTION_HEADING_RE.finditer(_mask_fenced_blocks(text)))
    return [
        (
            heading.group(1).strip(),
            text[
                heading.end() : (
                    headings[index + 1].start()
                    if index + 1 < len(headings)
                    else len(text)
                )
            ].strip(),
        )
        for index, heading in enumerate(headings)
    ]


def section_text(item: ProjectItem, name: str) -> str:
    return next(
        (content for heading, content in _sections(item.body) if heading == name),
        "",
    )


def _validation_section_text(item: ProjectItem, name: str) -> str:
    return _mask_fenced_blocks(section_text(item, name)).strip()


def _acceptance_criteria_structure_valid(text: str) -> bool:
    criteria = LIST_ITEM_RE.findall(text)
    if not criteria:
        return False
    return all(
        TASK_CHECKBOX_RE.fullmatch(criterion.strip()) is not None
        for criterion in criteria
    )


def _acceptance_criteria_all_checked(text: str) -> bool:
    checkboxes = [
        TASK_CHECKBOX_RE.fullmatch(criterion.strip())
        for criterion in LIST_ITEM_RE.findall(text)
    ]
    return all(checkbox is not None and checkbox.group(1) != " " for checkbox in checkboxes)


def load_milestones(path: Path) -> tuple[set[str], list[ProjectIssue]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return set(), [_issue(path, f"roadmap.md を読めません: {exc}")]
    return set(MILESTONE_RE.findall(_mask_fenced_blocks(text))), []


def validate_milestones(
    items: list[ProjectItem], milestones: set[str]
) -> list[ProjectIssue]:
    return [
        _issue(item.path, f"roadmap にマイルストーンがありません: {item.milestone}")
        for item in items
        if item.milestone not in milestones
    ]


def render_backlog(items: list[ProjectItem]) -> str:
    rows = [
        "# SheetLens 改善 Backlog",
        "",
        "> このファイルは `scripts/check_project_state.py render` で生成します。手動編集しません。",
        "",
        "| ID | 優先度 | 状態 | マイルストーン | 課題 | 依存 | 担当 |",
        "|---|---|---|---|---|---|---|",
    ]
    ordered = sorted(
        items,
        key=lambda item: (
            PRIORITY_ORDER[item.priority],
            item.milestone,
            item.id,
        ),
    )
    for item in ordered:
        deps = ", ".join(item.depends_on) or "—"
        owner = item.owner or "—"
        rows.append(
            f"| [{item.id}](items/{item.path.name}) | {item.priority} | {item.status} | "
            f"{item.milestone} | {item.title} | {deps} | {owner} |"
        )
    return "\n".join(rows) + "\n"


def validate_backlog(path: Path, expected: str) -> list[ProjectIssue]:
    actual = path.read_bytes() if path.exists() else b""
    return (
        []
        if actual == expected.encode("utf-8")
        else [_issue(path, "backlog.md が課題ファイルと同期していません")]
    )


def write_backlog(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".backlog-", dir=path.parent, text=True)
    try:
        try:
            handle = os.fdopen(fd, "w", encoding="utf-8", newline="\n")
        except BaseException:
            try:
                os.close(fd)
            except OSError as exc:
                if exc.errno != errno.EBADF:
                    raise
            raise
        with handle:
            handle.write(text)
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def dependency_closure(item_id: str, by_id: dict[str, ProjectItem]) -> set[str]:
    """Return declared dependencies, traversing only nodes present in ``by_id``."""
    seen: set[str] = set()
    item = by_id.get(item_id)
    stack = list(item.depends_on) if item else []
    while stack:
        dep = stack.pop()
        if dep in seen:
            continue
        seen.add(dep)
        if dep in by_id:
            stack.extend(by_id[dep].depends_on)
    return seen


def _graph_index(items: list[ProjectItem]) -> tuple[dict[str, ProjectItem], set[str]]:
    grouped: dict[str, list[ProjectItem]] = {}
    for item in items:
        grouped.setdefault(item.id, []).append(item)
    duplicate_ids = {item_id for item_id, matches in grouped.items() if len(matches) > 1}
    by_id = {
        item_id: matches[0]
        for item_id, matches in grouped.items()
        if item_id not in duplicate_ids
    }
    return by_id, duplicate_ids


def eligible_items(items: list[ProjectItem]) -> list[ProjectItem]:
    by_id, _ = _graph_index(items)
    return sorted(
        (
            item
            for item in by_id.values()
            if item.status == "ready"
            and all(
                dep in by_id and by_id[dep].status == "done"
                for dep in item.depends_on
            )
        ),
        key=lambda item: (PRIORITY_ORDER[item.priority], item.milestone, item.id),
    )


def _normalized_parts(value: str) -> tuple[str, ...]:
    normalized = Path(value).as_posix().strip("/")
    if normalized == ".":
        return ()
    return tuple(part.casefold() for part in normalized.split("/") if part)


def paths_conflict(left: str, right: str) -> bool:
    left_parts = _normalized_parts(left)
    right_parts = _normalized_parts(right)
    shortest = min(len(left_parts), len(right_parts))
    return left_parts[:shortest] == right_parts[:shortest]


def validate_parallel_work(items: list[ProjectItem]) -> list[ProjectIssue]:
    issues: list[ProjectIssue] = []
    by_id, _ = _graph_index(items)
    active = sorted(
        (item for item in by_id.values() if item.status == "in_progress"),
        key=lambda item: (item.id, item.path.as_posix()),
    )
    for index, left in enumerate(active):
        for right in active[index + 1 :]:
            if left.owner is not None and left.owner == right.owner:
                issues.append(
                    _issue(right.path, f"{left.id} と owner が重複しています: {right.owner}")
                )
            left_deps = dependency_closure(left.id, by_id)
            right_deps = dependency_closure(right.id, by_id)
            if right.id in left_deps or left.id in right_deps:
                issues.append(
                    _issue(
                        right.path,
                        f"{left.id} と {right.id} は依存関係があるため並行実行できません",
                    )
                )
            for left_path in sorted(left.touches):
                for right_path in sorted(right.touches):
                    if paths_conflict(left_path, right_path):
                        issues.append(
                            _issue(
                                right.path,
                                f"{left.id} と {right.id} の touches が競合しています: "
                                f"{left_path} <-> {right_path}",
                            )
                        )
    return issues


def _cycles(by_id: dict[str, ProjectItem]) -> list[list[str]]:
    visiting: list[str] = []
    visited: set[str] = set()
    found: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    def visit(item_id: str) -> None:
        if item_id in visiting:
            start = visiting.index(item_id)
            nodes = visiting[start:]
            rotations = [
                tuple(nodes[index:] + nodes[:index]) for index in range(len(nodes))
            ]
            canonical = min(rotations)
            if canonical not in seen:
                seen.add(canonical)
                found.append([*canonical, canonical[0]])
            return
        if item_id in visited or item_id not in by_id:
            return
        visiting.append(item_id)
        for dep in sorted(by_id[item_id].depends_on):
            visit(dep)
        visiting.pop()
        visited.add(item_id)

    for item_id in sorted(by_id):
        visit(item_id)
    return sorted(found)


def validate_items(items: list[ProjectItem]) -> list[ProjectIssue]:
    issues: list[ProjectIssue] = []
    by_id, duplicate_ids = _graph_index(items)
    duplicate_items = sorted(
        (item for item in items if item.id in duplicate_ids),
        key=lambda item: (item.id, str(item.path)),
    )
    issues.extend(
        _issue(item.path, f"課題 ID が重複しています: {item.id}")
        for item in duplicate_items
    )
    for item in items:
        for dep in item.depends_on:
            if dep in duplicate_ids:
                issues.append(
                    _issue(item.path, f"依存先の課題 ID が重複しています: {dep}")
                )
            elif dep not in by_id:
                issues.append(_issue(item.path, f"依存先が存在しません: {dep}"))
        required_sections = (
            "背景と根本原因",
            "根拠",
            "受け入れ条件",
            "対象外",
            "実装計画",
            "完了証拠",
        )
        for name in required_sections:
            headings = {heading for heading, _ in _sections(item.body)}
            if name not in headings:
                issues.append(_issue(item.path, f"必須セクションがありません: {name}"))
        if item.status in {"ready", "in_progress", "blocked", "done"}:
            for name in ("背景と根本原因", "受け入れ条件", "対象外"):
                if not _validation_section_text(item, name):
                    issues.append(_issue(item.path, f"{item.status} では {name} を記載してください"))
            if not item.touches:
                issues.append(_issue(item.path, f"{item.status} では touches が必須です"))
        acceptance = _validation_section_text(item, "受け入れ条件")
        if (
            item.status in {"ready", "in_progress", "blocked"}
            and acceptance
            and not _acceptance_criteria_structure_valid(acceptance)
        ):
            issues.append(
                _issue(
                    item.path,
                    f"{item.status} では受け入れ条件をチェックボックスで記載してください",
                )
            )
        if item.status == "in_progress" and not item.owner:
            issues.append(_issue(item.path, "status=in_progress では owner が必須です"))
        if item.status != "in_progress" and item.owner is not None:
            issues.append(_issue(item.path, "owner は in_progress のときだけ設定できます"))
        if item.status == "blocked":
            blocker = _validation_section_text(item, "ブロッカー")
            for label in ("理由", "解除条件", "次に確認すること"):
                if not re.search(rf"^- {label}:\s*\S", blocker, re.M):
                    issues.append(_issue(item.path, f"blocked では {label} を記載してください"))
        if item.status == "cancelled" and not _validation_section_text(item, "中止理由"):
            issues.append(_issue(item.path, "cancelled では中止理由を記載してください"))
        if item.id in by_id and item.status in {"ready", "in_progress", "done"}:
            incomplete = [
                dep
                for dep in item.depends_on
                if dep in by_id and by_id[dep].status != "done"
            ]
            for dep in incomplete:
                issues.append(_issue(item.path, f"未完了の依存課題があります: {dep}"))
        if item.status == "done":
            if (
                not _acceptance_criteria_structure_valid(acceptance)
                or not _acceptance_criteria_all_checked(acceptance)
            ):
                issues.append(
                    _issue(item.path, "done では受け入れ条件をすべてチェックしてください")
                )
            if not _validation_section_text(item, "完了証拠"):
                issues.append(_issue(item.path, "done では完了証拠を記録してください"))
    for cycle in _cycles(by_id):
        issues.append(
            _issue(
                by_id[cycle[0]].path,
                f"依存関係が循環しています: {' -> '.join(cycle)}",
            )
        )
    return issues


def _print_issues(issues: list[ProjectIssue], root: Path) -> None:
    grouped: dict[Path, list[str]] = {}
    for issue in issues:
        grouped.setdefault(issue.path, []).append(issue.message)
    for path in sorted(grouped):
        try:
            label = path.relative_to(root)
        except ValueError:
            label = path
        print(f"{label}:")
        for message in grouped[path]:
            print(f"  - {message}")


def run(command: str, root: Path) -> int:
    project = root / "docs" / "project"
    items, issues = load_items(project / "items")
    milestones, milestone_issues = load_milestones(project / "roadmap.md")
    issues.extend(milestone_issues)
    issues.extend(validate_milestones(items, milestones))
    issues.extend(validate_items(items))
    issues.extend(validate_parallel_work(items))
    if issues:
        _print_issues(issues, root)
        return 1

    if command == "check":
        issues.extend(
            validate_backlog(project / "backlog.md", render_backlog(items))
        )
        if issues:
            _print_issues(issues, root)
            return 1
    elif command == "render":
        backlog = project / "backlog.md"
        write_backlog(backlog, render_backlog(items))
        print(f"生成しました: {backlog}")
    elif command == "next":
        by_id, _ = _graph_index(items)
        active = sorted(
            (item for item in by_id.values() if item.status == "in_progress"),
            key=lambda item: (item.id, item.path.as_posix()),
        )
        for item in eligible_items(items):
            conflicts = [
                other.id
                for other in active
                if any(
                    paths_conflict(left, right)
                    for left in item.touches
                    for right in other.touches
                )
            ]
            suffix = (
                f" / 競合: {', '.join(conflicts)}" if conflicts else " / 並行可能"
            )
            print(f"{item.priority} {item.id} {item.title}{suffix}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SheetLens 改善プロジェクト状態を検証する"
    )
    parser.add_argument("command", choices=("check", "render", "next"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    return run(args.command, args.root.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
