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
