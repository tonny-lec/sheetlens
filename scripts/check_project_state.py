from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

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
ID_RE = re.compile(r"SL-\d{3}\Z")
FRONT_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.S)
SECTION_RE = re.compile(r"^## ([^\n]+)\r?\n(.*?)(?=^## |\Z)", re.M | re.S)
CHECKBOX_RE = re.compile(r"^\s*-\s+\[([ xX])\]", re.M)
MILESTONE_RE = re.compile(r"^## (M[1-4])(?:\s|$)", re.M)


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


def parse_item(path: Path) -> tuple[ProjectItem | None, list[ProjectIssue]]:
    text = path.read_text(encoding="utf-8")
    match = FRONT_RE.match(text)
    if not match:
        return None, [_issue(path, "YAML front matter を解析できません")]
    try:
        raw = yaml.safe_load(match.group(1))
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


def section_text(item: ProjectItem, name: str) -> str:
    return next(
        (
            content.strip()
            for heading, content in SECTION_RE.findall(item.body)
            if heading.strip() == name
        ),
        "",
    )


def load_milestones(path: Path) -> tuple[set[str], list[ProjectIssue]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return set(), [_issue(path, f"roadmap.md を読めません: {exc}")]
    return set(MILESTONE_RE.findall(text)), []


def validate_milestones(
    items: list[ProjectItem], milestones: set[str]
) -> list[ProjectIssue]:
    return [
        _issue(item.path, f"roadmap にマイルストーンがありません: {item.milestone}")
        for item in items
        if item.milestone not in milestones
    ]


def dependency_closure(item_id: str, by_id: dict[str, ProjectItem]) -> set[str]:
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


def _cycles(items: list[ProjectItem]) -> list[list[str]]:
    by_id = {item.id: item for item in items}
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
        for dep in by_id[item_id].depends_on:
            visit(dep)
        visiting.pop()
        visited.add(item_id)

    for item in items:
        visit(item.id)
    return found


def validate_items(items: list[ProjectItem]) -> list[ProjectIssue]:
    issues: list[ProjectIssue] = []
    by_id: dict[str, ProjectItem] = {}
    for item in items:
        if item.id in by_id:
            issues.append(_issue(item.path, f"課題 ID が重複しています: {item.id}"))
        else:
            by_id[item.id] = item
    for item in items:
        for dep in item.depends_on:
            if dep not in by_id:
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
            headings = {heading.strip() for heading, _ in SECTION_RE.findall(item.body)}
            if name not in headings:
                issues.append(_issue(item.path, f"必須セクションがありません: {name}"))
        if item.status in {"ready", "in_progress", "blocked", "done"}:
            for name in ("背景と根本原因", "受け入れ条件", "対象外"):
                if not section_text(item, name):
                    issues.append(_issue(item.path, f"{item.status} では {name} を記載してください"))
            if not item.touches:
                issues.append(_issue(item.path, f"{item.status} では touches が必須です"))
        if item.status == "in_progress" and not item.owner:
            issues.append(_issue(item.path, "status=in_progress では owner が必須です"))
        if item.status != "in_progress" and item.owner is not None:
            issues.append(_issue(item.path, "owner は in_progress のときだけ設定できます"))
        if item.status == "blocked":
            blocker = section_text(item, "ブロッカー")
            for label in ("理由", "解除条件", "次に確認すること"):
                if not re.search(rf"^- {label}:\s*\S", blocker, re.M):
                    issues.append(_issue(item.path, f"blocked では {label} を記載してください"))
        if item.status == "cancelled" and not section_text(item, "中止理由"):
            issues.append(_issue(item.path, "cancelled では中止理由を記載してください"))
        if item.status in {"ready", "in_progress", "done"}:
            incomplete = [
                dep
                for dep in item.depends_on
                if dep in by_id and by_id[dep].status != "done"
            ]
            for dep in incomplete:
                issues.append(_issue(item.path, f"未完了の依存課題があります: {dep}"))
        if item.status == "done":
            boxes = CHECKBOX_RE.findall(section_text(item, "受け入れ条件"))
            if not boxes or any(box == " " for box in boxes):
                issues.append(
                    _issue(item.path, "done では受け入れ条件をすべてチェックしてください")
                )
            if not section_text(item, "完了証拠"):
                issues.append(_issue(item.path, "done では完了証拠を記録してください"))
    for cycle in _cycles(items):
        issues.append(
            _issue(
                by_id[cycle[0]].path,
                f"依存関係が循環しています: {' -> '.join(cycle)}",
            )
        )
    return issues
