# SheetLens Project Management Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Markdown 課題を正本として検証、backlog 生成、着手可能課題表示を行うリポジトリ内プロジェクト管理基盤を構築する。

**Architecture:** `scripts/check_project_state.py` を import 可能な小さな CLI モジュールとして実装し、課題解析、状態・依存検証、並行競合検証、決定的な backlog 生成を純粋関数へ分離する。`docs/project/items/*.md` だけを正本とし、`backlog.md` は検証済み課題からアトミックに生成する。

**Tech Stack:** Python 3.12+、標準ライブラリ、PyYAML、pytest、Ruff

## Global Constraints

- 実行開始前に書き込み可能な Git 環境で専用 branch/worktree を作る。`main` に直接コミットしない。
- 新しい依存を追加しない。既存の PyYAML、pytest、Ruff だけを使う。
- `docs/project/items/*.md` を唯一の正本とし、別の JSON/YAML 台帳を作らない。
- `backlog.md` は生成物とし、手動編集を許可しない。
- bootstrap 期間は、親ワーカーが明示した管理ファイルの新規作成を実装サブエージェントへ委譲できる。
- 基盤の検証完了後は、親ワーカーだけが管理ファイルの状態、担当、依存、backlog を更新する。
- TDD の red-green-refactor を各タスクで実施する。

---

### Task 1: 課題 Markdown の解析モデル

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/check_project_state.py`
- Create: `tests/test_project_state.py`

**Interfaces:**
- Consumes: `Path` で示された `docs/project/items/*.md`
- Produces: `ProjectItem`、`ProjectIssue`、`parse_item(path)`、`load_items(items_dir)`

- [ ] **Step 1: 正常・異常 front matter の失敗テストを書く**

```python
# tests/test_project_state.py
from pathlib import Path

from scripts.check_project_state import load_items, parse_item


def write_item(path: Path, front: str, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{front.strip()}\n---\n{body}", encoding="utf-8")


def valid_front(item_id: str = "SL-001") -> str:
    return f"""
id: {item_id}
title: 安定質問ID
status: proposed
priority: P1
type: defect
milestone: M1
depends_on: []
touches: []
owner: null
"""


def test_parse_item_returns_typed_item(tmp_path: Path) -> None:
    path = tmp_path / "SL-001-stable-id.md"
    write_item(path, valid_front(), "# SL-001 安定質問ID\n")

    item, issues = parse_item(path)

    assert issues == []
    assert item is not None
    assert item.id == "SL-001"
    assert item.depends_on == ()
    assert item.owner is None


def test_parse_item_reports_unknown_key_and_bad_filename(tmp_path: Path) -> None:
    path = tmp_path / "wrong.md"
    write_item(path, valid_front() + "\nunknown: value")

    item, issues = parse_item(path)

    assert item is None
    assert [issue.message for issue in issues] == [
        "未知の front matter キーです: unknown",
        "ファイル名は SL-001- で始めてください",
    ]
```

- [ ] **Step 2: テストを実行して未実装で失敗することを確認する**

Run: `uv run pytest tests/test_project_state.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.check_project_state'`

- [ ] **Step 3: データモデルと parser を実装する**

```python
# scripts/check_project_state.py
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

ALLOWED_KEYS = {
    "id", "title", "status", "priority", "type", "milestone",
    "depends_on", "touches", "owner",
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

    issues = [_issue(path, f"未知の front matter キーです: {key}")
              for key in sorted(set(raw) - ALLOWED_KEYS)]
    required = ALLOWED_KEYS
    issues.extend(_issue(path, f"必須キーがありません: {key}")
                  for key in sorted(required - set(raw)))

    item_id = raw.get("id")
    if isinstance(item_id, str) and not path.name.startswith(f"{item_id}-"):
        issues.append(_issue(path, f"ファイル名は {item_id}- で始めてください"))
    if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
        issues.append(_issue(path, "id は SL-001 形式で指定してください"))

    scalar_rules = {
        "title": str, "status": str, "priority": str,
        "type": str, "milestone": str,
    }
    for key, expected in scalar_rules.items():
        if key in raw and not isinstance(raw[key], expected):
            issues.append(_issue(path, f"{key} の型が不正です"))
    for key in ("depends_on", "touches"):
        if key in raw and (not isinstance(raw[key], list)
                           or not all(isinstance(value, str) for value in raw[key])):
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
```

- [ ] **Step 4: parser テストを通す**

Run: `uv run pytest tests/test_project_state.py -v`

Expected: PASS

- [ ] **Step 5: Task 1 をコミットする**

```bash
git add scripts/__init__.py scripts/check_project_state.py tests/test_project_state.py
git commit -m "feat: add project item parser"
```

### Task 2: 状態、本文、依存グラフの検証

> **Completed at `beb5d29`:** 以下のコード例は初期実装の履歴であり、再適用しない。
> 現在の `scripts/check_project_state.py` を正とする。承認済み実装は fence-aware section parsing、
> validation-only masking、duplicate-free `_graph_index()`、入力順に依存しない cycle、
> CommonMark 全 list marker の checkbox 検証を含む。後続タスクはこの invariant を維持する。

承認済み regression は fenced heading/content、duplicate-ID graph 除外と曖昧依存、node/edge
順を反転しても一定の cycle、`-`、`*`、`+`、`N.`、`N)` の checked/plain/empty/unchecked
item をカバーしている。

**Files:**
- Modify: `scripts/check_project_state.py`
- Modify: `tests/test_project_state.py`

**Interfaces:**
- Consumes: `list[ProjectItem]`
- Produces: `section_text()`、`validate_items()`、`dependency_closure()`

- [ ] **Step 1: 重複、循環、状態別要件の失敗テストを追加する**

```python
from scripts.check_project_state import ProjectItem, validate_items, validate_milestones


def ready_body() -> str:
    return """# SL-001 課題

## 背景と根本原因
原因が確認されている。

## 根拠
src/example.py:10

## 受け入れ条件
- [ ] 挙動を修正する

## 対象外
互換性移行以外は扱わない。

## 実装計画
着手時に作成する。

## 完了証拠
"""


def test_validate_items_reports_cycle_and_invalid_done(tmp_path: Path) -> None:
    first = ProjectItem(tmp_path / "SL-001-a.md", "SL-001", "A", "done", "P1",
                        "defect", "M1", ("SL-002",), ("src/a.py",), None,
                        ready_body())
    second = ProjectItem(tmp_path / "SL-002-b.md", "SL-002", "B", "ready", "P1",
                         "defect", "M1", ("SL-001",), ("src/b.py",), None,
                         ready_body())

    messages = [issue.message for issue in validate_items([first, second])]

    assert "依存関係が循環しています: SL-001 -> SL-002 -> SL-001" in messages
    assert "done では受け入れ条件をすべてチェックしてください" in messages
    assert "done では完了証拠を記録してください" in messages


def test_validate_items_reports_each_disjoint_cycle(tmp_path: Path) -> None:
    items = [
        ProjectItem(tmp_path / "SL-001.md", "SL-001", "A", "proposed", "P1",
                    "defect", "M1", ("SL-002",), (), None, ""),
        ProjectItem(tmp_path / "SL-002.md", "SL-002", "B", "proposed", "P1",
                    "defect", "M1", ("SL-001",), (), None, ""),
        ProjectItem(tmp_path / "SL-003.md", "SL-003", "C", "proposed", "P1",
                    "defect", "M1", ("SL-004",), (), None, ""),
        ProjectItem(tmp_path / "SL-004.md", "SL-004", "D", "proposed", "P1",
                    "defect", "M1", ("SL-003",), (), None, ""),
    ]

    cycle_messages = [issue.message for issue in validate_items(items)
                      if issue.message.startswith("依存関係が循環しています")]

    assert cycle_messages == [
        "依存関係が循環しています: SL-001 -> SL-002 -> SL-001",
        "依存関係が循環しています: SL-003 -> SL-004 -> SL-003",
    ]


def test_validate_milestones_reports_missing_roadmap_heading(tmp_path: Path) -> None:
    item = ProjectItem(tmp_path / "SL-001.md", "SL-001", "A", "proposed", "P1",
                       "defect", "M2", (), (), None, "")

    issues = validate_milestones([item], {"M1"})

    assert [issue.message for issue in issues] == ["roadmap にマイルストーンがありません: M2"]
```

- [ ] **Step 2: 追加テストが失敗することを確認する**

Run: `uv run pytest tests/test_project_state.py::test_validate_items_reports_cycle_and_invalid_done -v`

Expected: FAIL with `ImportError: cannot import name 'validate_items'`

- [ ] **Step 3: 本文と依存グラフの検証を実装する**

```python
SECTION_RE = re.compile(r"^## ([^\n]+)\r?\n(.*?)(?=^## |\Z)", re.M | re.S)
CHECKBOX_RE = re.compile(r"^\s*-\s+\[([ xX])\]", re.M)
MILESTONE_RE = re.compile(r"^## (M[1-4])(?:\s|$)", re.M)


def section_text(item: ProjectItem, name: str) -> str:
    return next((content.strip() for heading, content in SECTION_RE.findall(item.body)
                 if heading.strip() == name), "")


def load_milestones(path: Path) -> tuple[set[str], list[ProjectIssue]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return set(), [_issue(path, f"roadmap.md を読めません: {exc}")]
    return set(MILESTONE_RE.findall(text)), []


def validate_milestones(items: list[ProjectItem], milestones: set[str]) -> list[ProjectIssue]:
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
            rotations = [tuple(nodes[index:] + nodes[:index]) for index in range(len(nodes))]
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
        required_sections = ("背景と根本原因", "根拠", "受け入れ条件", "対象外", "実装計画", "完了証拠")
        for name in required_sections:
            if name not in {heading.strip() for heading, _ in SECTION_RE.findall(item.body)}:
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
            incomplete = [dep for dep in item.depends_on
                          if dep in by_id and by_id[dep].status != "done"]
            for dep in incomplete:
                issues.append(_issue(item.path, f"未完了の依存課題があります: {dep}"))
        if item.status == "done":
            boxes = CHECKBOX_RE.findall(section_text(item, "受け入れ条件"))
            if not boxes or any(box == " " for box in boxes):
                issues.append(_issue(item.path, "done では受け入れ条件をすべてチェックしてください"))
            if not section_text(item, "完了証拠"):
                issues.append(_issue(item.path, "done では完了証拠を記録してください"))
    for cycle in _cycles(items):
        issues.append(_issue(by_id[cycle[0]].path, f"依存関係が循環しています: {' -> '.join(cycle)}"))
    return issues
```

- [ ] **Step 4: 状態・依存テストを通す**

Run: `uv run pytest tests/test_project_state.py -v`

Expected: PASS

- [ ] **Step 5: Task 2 をコミットする**

```bash
git add scripts/check_project_state.py tests/test_project_state.py
git commit -m "feat: validate project item states"
```

### Task 3: 並行作業の競合検証

**Files:**
- Modify: `scripts/check_project_state.py`
- Modify: `tests/test_project_state.py`

**Interfaces:**
- Consumes: `in_progress` の `depends_on`、`touches`、`owner` と Task 2 の duplicate-free `_graph_index()`
- Produces: `paths_conflict()`、`validate_parallel_work()`

- [ ] **Step 1: 推移的依存、親子パス、owner 重複、決定性、重複 ID 除外の失敗テストを書く**

```python
from scripts.check_project_state import validate_parallel_work


def test_parallel_work_rejects_transitive_dependency_and_parent_path(tmp_path: Path) -> None:
    first = ProjectItem(tmp_path / "SL-001-a.md", "SL-001", "A", "in_progress", "P1",
                        "defect", "M1", (), ("src/sheetlens",), "worker-a", ready_body())
    middle = ProjectItem(tmp_path / "SL-002-b.md", "SL-002", "B", "done", "P1",
                         "defect", "M1", ("SL-001",), ("tests/b.py",), None,
                         ready_body().replace("- [ ]", "- [x]") + "\ncommand: passed\n")
    last = ProjectItem(tmp_path / "SL-003-c.md", "SL-003", "C", "in_progress", "P1",
                       "defect", "M1", ("SL-002",), ("src/sheetlens/reader/a.py",),
                       "worker-c", ready_body())

    messages = [issue.message for issue in validate_parallel_work([first, middle, last])]
    reversed_messages = [
        issue.message for issue in validate_parallel_work([last, middle, first])
    ]

    assert messages == reversed_messages
    assert "SL-001 と SL-003 は依存関係があるため並行実行できません" in messages
    assert "SL-001 と SL-003 の touches が競合しています: src/sheetlens <-> src/sheetlens/reader/a.py" in messages


def test_parallel_work_rejects_duplicate_non_null_owner(tmp_path: Path) -> None:
    first = ProjectItem(tmp_path / "SL-001-a.md", "SL-001", "A", "in_progress", "P1",
                        "defect", "M1", (), ("src/a.py",), "worker-a", ready_body())
    second = ProjectItem(tmp_path / "SL-002-b.md", "SL-002", "B", "in_progress", "P1",
                         "defect", "M1", (), ("src/b.py",), "worker-a", ready_body())

    messages = [issue.message for issue in validate_parallel_work([second, first])]

    assert messages == ["SL-001 と owner が重複しています: worker-a"]


def test_parallel_work_is_deterministic_and_excludes_duplicate_ids(tmp_path: Path) -> None:
    duplicate_a = ProjectItem(
        tmp_path / "SL-001-a.md", "SL-001", "A", "in_progress", "P1", "defect", "M1",
        (), ("src/a.py",), "worker-a", ready_body(),
    )
    duplicate_b = ProjectItem(
        tmp_path / "SL-001-b.md", "SL-001", "B", "in_progress", "P1", "defect", "M1",
        ("SL-002",), ("src/b.py",), "worker-b", ready_body(),
    )
    unique = ProjectItem(
        tmp_path / "SL-002.md", "SL-002", "C", "in_progress", "P1", "defect", "M1",
        (), ("src/c.py",), "worker-c", ready_body(),
    )

    forward = validate_parallel_work([duplicate_a, duplicate_b, unique])
    reverse = validate_parallel_work([unique, duplicate_b, duplicate_a])

    assert forward == reverse == []
```

- [ ] **Step 2: テストが未実装で失敗することを確認する**

Run: `uv run pytest tests/test_project_state.py::test_parallel_work_rejects_transitive_dependency_and_parent_path -v`

Expected: FAIL with `ImportError: cannot import name 'validate_parallel_work'`

- [ ] **Step 3: 並行競合検証を実装する**

```python
def _normalized_parts(value: str) -> tuple[str, ...]:
    return tuple(part for part in Path(value).as_posix().strip("/").split("/") if part)


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
        for right in active[index + 1:]:
            if left.owner is not None and left.owner == right.owner:
                issues.append(_issue(right.path, f"{left.id} と owner が重複しています: {right.owner}"))
            left_deps = dependency_closure(left.id, by_id)
            right_deps = dependency_closure(right.id, by_id)
            if right.id in left_deps or left.id in right_deps:
                issues.append(_issue(right.path,
                                     f"{left.id} と {right.id} は依存関係があるため並行実行できません"))
            for left_path in sorted(left.touches):
                for right_path in sorted(right.touches):
                    if paths_conflict(left_path, right_path):
                        issues.append(_issue(
                            right.path,
                            f"{left.id} と {right.id} の touches が競合しています: "
                            f"{left_path} <-> {right_path}",
                        ))
    return issues
```

- [ ] **Step 4: 並行競合テストを通す**

Run: `uv run pytest tests/test_project_state.py -v`

Expected: PASS

- [ ] **Step 5: Task 3 をコミットする**

```bash
git add scripts/check_project_state.py tests/test_project_state.py
git commit -m "feat: validate parallel project work"
```

### Task 4: Backlog の決定的・アトミック生成

**Files:**
- Modify: `scripts/check_project_state.py`
- Modify: `tests/test_project_state.py`

**Interfaces:**
- Consumes: Task 2/3 の検証を通過した `list[ProjectItem]`
- Produces: `render_backlog(items)`、`write_backlog(path, text)`、`validate_backlog()`

- [ ] **Step 1: 並び順、リンク、stale 検出のテストを書く**

```python
from scripts.check_project_state import render_backlog, validate_backlog, write_backlog


def test_render_backlog_is_sorted_and_detects_stale_file(tmp_path: Path) -> None:
    low = ProjectItem(tmp_path / "SL-002-low.md", "SL-002", "Low", "proposed", "P2",
                      "quality", "M2", (), (), None, "")
    high = ProjectItem(tmp_path / "SL-001-high.md", "SL-001", "High", "ready", "P1",
                       "defect", "M1", (), ("src/a.py",), None, ready_body())
    backlog = tmp_path / "backlog.md"
    backlog.write_text("stale\n", encoding="utf-8")

    rendered = render_backlog([low, high])
    issues = validate_backlog(backlog, rendered)

    assert rendered.index("SL-001") < rendered.index("SL-002")
    assert "[SL-001](items/SL-001-high.md)" in rendered
    assert [issue.message for issue in issues] == ["backlog.md が課題ファイルと同期していません"]

    write_backlog(backlog, rendered)
    assert backlog.read_text(encoding="utf-8") == rendered
```

- [ ] **Step 2: 未実装で失敗することを確認する**

Run: `uv run pytest tests/test_project_state.py::test_render_backlog_is_sorted_and_detects_stale_file -v`

Expected: FAIL with `ImportError: cannot import name 'render_backlog'`

- [ ] **Step 3: backlog 生成と置換を実装する**

```python
import os
import tempfile

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def render_backlog(items: list[ProjectItem]) -> str:
    rows = [
        "# SheetLens 改善 Backlog",
        "",
        "> このファイルは `scripts/check_project_state.py render` で生成します。手動編集しません。",
        "",
        "| ID | 優先度 | 状態 | マイルストーン | 課題 | 依存 | 担当 |",
        "|---|---|---|---|---|---|---|",
    ]
    ordered = sorted(items, key=lambda item: (PRIORITY_ORDER[item.priority], item.milestone, item.id))
    for item in ordered:
        deps = ", ".join(item.depends_on) or "—"
        owner = item.owner or "—"
        rows.append(
            f"| [{item.id}](items/{item.path.name}) | {item.priority} | {item.status} | "
            f"{item.milestone} | {item.title} | {deps} | {owner} |"
        )
    return "\n".join(rows) + "\n"


def validate_backlog(path: Path, expected: str) -> list[ProjectIssue]:
    actual = path.read_text(encoding="utf-8") if path.exists() else ""
    return [] if actual == expected else [_issue(path, "backlog.md が課題ファイルと同期していません")]


def write_backlog(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".backlog-", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
```

- [ ] **Step 4: backlog テストを通す**

Run: `uv run pytest tests/test_project_state.py -v`

Expected: PASS

- [ ] **Step 5: Task 4 をコミットする**

```bash
git add scripts/check_project_state.py tests/test_project_state.py
git commit -m "feat: render project backlog"
```

### Task 5: check、render、next CLI

**Files:**
- Modify: `scripts/check_project_state.py`
- Modify: `tests/test_project_state.py`

**Interfaces:**
- Consumes: Task 2 の duplicate-free `_graph_index()` と Task 3/4 の validator/renderer
- Produces: `eligible_items()`、`run(command, root)`、`main(argv)`

- [ ] **Step 1: eligibility、CLI の終了コード、next 順序のテストを書く**

```python
from scripts.check_project_state import eligible_items, run


def test_next_returns_only_unblocked_ready_items(tmp_path: Path, capsys) -> None:
    project = tmp_path / "docs" / "project"
    items_dir = project / "items"
    project.mkdir(parents=True)
    (project / "roadmap.md").write_text("## M1 Test\n## M2 Test\n", encoding="utf-8")
    write_item(items_dir / "SL-001-first.md", valid_front().replace("status: proposed", "status: ready")
               .replace("touches: []", "touches: [src/a.py]"), ready_body())
    second_front = valid_front("SL-002")
    second_front = second_front.replace("depends_on: []", "depends_on: [SL-001]")
    second_front = second_front.replace("touches: []", "touches: [src/b.py]")
    write_item(items_dir / "SL-002-second.md", second_front, ready_body())
    third_front = valid_front("SL-003").replace("status: proposed", "status: ready")
    third_front = third_front.replace("priority: P1", "priority: P0")
    third_front = third_front.replace("milestone: M1", "milestone: M2")
    third_front = third_front.replace("touches: []", "touches: [src/c.py]")
    write_item(items_dir / "SL-003-third.md", third_front, ready_body())
    fourth_front = valid_front("SL-004").replace("status: proposed", "status: ready")
    fourth_front = fourth_front.replace("touches: []", "touches: [src/d.py]")
    write_item(items_dir / "SL-004-fourth.md", fourth_front, ready_body())
    fifth_front = valid_front("SL-005").replace("status: proposed", "status: ready")
    fifth_front = fifth_front.replace("milestone: M1", "milestone: M2")
    fifth_front = fifth_front.replace("touches: []", "touches: [src/e.py]")
    write_item(items_dir / "SL-005-fifth.md", fifth_front, ready_body())
    (project / "backlog.md").write_text("", encoding="utf-8")

    code = run("next", tmp_path)

    assert code == 0
    output = capsys.readouterr().out
    assert "SL-002" not in output
    assert [line for line in output.splitlines() if line.startswith("P")] == [
        "P0 SL-003 安定質問ID / 並行可能",
        "P1 SL-001 安定質問ID / 並行可能",
        "P1 SL-004 安定質問ID / 並行可能",
        "P1 SL-005 安定質問ID / 並行可能",
    ]


def test_eligible_items_excludes_non_done_missing_and_duplicate_dependencies(tmp_path: Path) -> None:
    done = ProjectItem(
        tmp_path / "SL-001.md", "SL-001", "Done", "done", "P1", "defect", "M1",
        (), ("src/done.py",), None,
        ready_body().replace("- [ ]", "- [x]") + "\ncommand: passed\n",
    )
    eligible = ProjectItem(
        tmp_path / "SL-002.md", "SL-002", "Eligible", "ready", "P1", "defect", "M1",
        ("SL-001",), ("src/eligible.py",), None, ready_body(),
    )
    pending = ProjectItem(
        tmp_path / "SL-003.md", "SL-003", "Pending", "proposed", "P1", "defect", "M1",
        (), (), None, ready_body(),
    )
    blocked = ProjectItem(
        tmp_path / "SL-004.md", "SL-004", "Blocked", "ready", "P1", "defect", "M1",
        ("SL-003",), ("src/blocked.py",), None, ready_body(),
    )
    missing = ProjectItem(
        tmp_path / "SL-005.md", "SL-005", "Missing", "ready", "P1", "defect", "M1",
        ("SL-999",), ("src/missing.py",), None, ready_body(),
    )
    duplicate_a = ProjectItem(
        tmp_path / "SL-006-a.md", "SL-006", "Duplicate A", "ready", "P1", "defect", "M1",
        (), ("src/a.py",), None, ready_body(),
    )
    duplicate_b = ProjectItem(
        tmp_path / "SL-006-b.md", "SL-006", "Duplicate B", "ready", "P1", "defect", "M1",
        (), ("src/b.py",), None, ready_body(),
    )
    ambiguous = ProjectItem(
        tmp_path / "SL-007.md", "SL-007", "Ambiguous", "ready", "P1", "defect", "M1",
        ("SL-006",), ("src/ambiguous.py",), None, ready_body(),
    )
    items = [ambiguous, duplicate_b, missing, pending, eligible, done, blocked, duplicate_a]

    assert [item.id for item in eligible_items(items)] == ["SL-002"]
    assert [item.id for item in eligible_items(list(reversed(items)))] == ["SL-002"]


def test_next_prints_no_candidates_when_duplicate_state_is_invalid(tmp_path: Path, capsys) -> None:
    project = tmp_path / "docs" / "project"
    items_dir = project / "items"
    project.mkdir(parents=True)
    (project / "roadmap.md").write_text("## M1 Test\n", encoding="utf-8")
    duplicate = valid_front().replace("status: proposed", "status: ready")
    duplicate = duplicate.replace("touches: []", "touches: [src/a.py]")
    write_item(items_dir / "SL-001-a.md", duplicate, ready_body())
    write_item(items_dir / "SL-001-b.md", duplicate, ready_body())
    (project / "backlog.md").write_text("", encoding="utf-8")

    assert run("next", tmp_path) == 1
    output = capsys.readouterr().out
    assert "課題 ID が重複しています: SL-001" in output
    assert " / 並行可能" not in output
```

- [ ] **Step 2: CLI テストが未実装で失敗することを確認する**

Run: `uv run pytest tests/test_project_state.py::test_next_returns_only_unblocked_ready_items -v`

Expected: FAIL with `ImportError: cannot import name 'run'`

- [ ] **Step 3: CLI を実装する**

```python
import argparse
from collections.abc import Sequence


def eligible_items(items: list[ProjectItem]) -> list[ProjectItem]:
    by_id, _ = _graph_index(items)
    return sorted(
        (item for item in by_id.values()
         if item.status == "ready"
         and all(dep in by_id and by_id[dep].status == "done"
                 for dep in item.depends_on)),
        key=lambda item: (PRIORITY_ORDER[item.priority], item.milestone, item.id),
    )


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
    rendered = render_backlog(items)
    if command == "check":
        issues.extend(validate_backlog(project / "backlog.md", rendered))
    if issues:
        _print_issues(issues, root)
        return 1
    if command == "render":
        write_backlog(project / "backlog.md", rendered)
        print(f"生成しました: {project / 'backlog.md'}")
    elif command == "next":
        active = [item for item in items if item.status == "in_progress"]
        for item in eligible_items(items):
            conflicts = [other.id for other in active
                         if any(paths_conflict(left, right)
                                for left in item.touches for right in other.touches)]
            suffix = f" / 競合: {', '.join(conflicts)}" if conflicts else " / 並行可能"
            print(f"{item.priority} {item.id} {item.title}{suffix}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SheetLens 改善プロジェクト状態を検証する")
    parser.add_argument("command", choices=("check", "render", "next"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    return run(args.command, args.root.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: CLI テストと lint を通す**

Run: `uv run pytest tests/test_project_state.py -v && uv run ruff check scripts tests/test_project_state.py`

Expected: PASS and `All checks passed!`

- [ ] **Step 5: Task 5 をコミットする**

```bash
git add scripts/check_project_state.py tests/test_project_state.py
git commit -m "feat: add project management CLI"
```

### Task 6: 運用文書、空の roadmap、開発者向け導線

**Files:**
- Create: `docs/project/README.md`
- Create: `docs/project/roadmap.md`
- Create: `docs/project/backlog.md`
- Modify: `CLAUDE.md`
- Test: `tests/test_project_state.py`

**Interfaces:**
- Consumes: Tasks 1-5 の CLI
- Produces: 初期課題登録計画が使う `docs/project/` 基盤

- [ ] **Step 1: 空プロジェクトの check/render/next E2E テストを書く**

```python
def test_empty_project_commands_are_deterministic(tmp_path: Path, capsys) -> None:
    project = tmp_path / "docs" / "project"
    (project / "items").mkdir(parents=True)
    (project / "roadmap.md").write_text(
        "## M1 A\n## M2 B\n## M3 C\n## M4 D\n", encoding="utf-8"
    )
    write_backlog(project / "backlog.md", render_backlog([]))

    assert run("check", tmp_path) == 0
    assert run("render", tmp_path) == 0
    assert run("next", tmp_path) == 0
    assert "SL-" not in capsys.readouterr().out
```

- [ ] **Step 2: `docs/project/README.md` に承認済み運用規約を書く**

次の内容で作成する。

````markdown
# SheetLens 改善プロジェクト

## 正本

`items/*.md` が課題状態の唯一の正本です。`backlog.md` は生成物なので手動編集しません。

## コマンド

```bash
uv run python scripts/check_project_state.py check
uv run python scripts/check_project_state.py render
uv run python scripts/check_project_state.py next
```

- `check`: 課題、依存関係、並行条件、backlog 同期を検証します。
- `render`: 検証成功後に backlog をアトミックに再生成します。
- `next`: 依存を満たした ready 課題と、現在の作業との競合を表示します。

`next` は候補表示前に全状態を検証します。エラーが 1 件でもあれば終了コード 1 を返し、
候補行や「並行可能」は表示しません。

終了コードは成功が 0、管理状態の不正が 1、CLI の使用方法の誤りが 2 です。

## 状態遷移

```text
proposed -> ready -> in_progress -> done
                         |
                         v
                      blocked

proposed / ready / blocked -> cancelled
done -> ready
```

- `proposed`: 根本原因、変更範囲、受け入れ条件のいずれかが未確定
- `ready`: 根拠、受け入れ条件、対象外、touches が明確で依存課題が完了
- `in_progress`: owner が割り当てられて作業中
- `blocked`: 理由、解除条件、次に確認することを記録して待機中
- `done`: 受け入れ条件と検証をすべて満たした
- `cancelled`: 中止理由を記録して終了

## 並行作業

複数課題を同時に進められるのは、直接・推移的な依存がなく、touches が競合せず、
owner が重複しない場合だけです。さらに、次の条件を守ります。

- 可変状態を共有せず、リポジトリ管理ファイルまたはプロジェクト管理ファイルを一切更新しない。
- 生成物を更新する課題は、互いに異なる生成物を対象とする場合でも必ず直列に実行する。
- 変更範囲が広い課題や、競合を静的に判断できない課題は直列に実行する。
- 同一ワークスペースでの並行実行は、変更範囲が完全に非重複の場合だけ許可する。それ以外は
  worktree を分離し、分離後も生成物と共有状態に関する直列実行の条件を守る。

親ワーカーだけが並行可否と状態を管理します。

## Bootstrap 期間

管理基盤の構築と初期課題登録が完了するまでの bootstrap 期間に限り、親ワーカーが
明示的に割り当てた管理ファイルの新規作成を実装ワーカーへ委譲できます。完了後は、
課題の状態、owner、依存関係、backlog を親ワーカーだけが更新します。

## 課題ファイル形式

```yaml
---
id: SL-001
title: 質問IDを再抽出後も安定させる
status: proposed
priority: P1
type: defect
milestone: M1
depends_on: []
touches: []
owner: null
---
```

本文には `背景と根本原因`、`根拠`、`受け入れ条件`、`対象外`、`実装計画`、
`完了証拠` の各セクションを置きます。受け入れ条件は Markdown チェックボックスで
記述します。backtick/tilde fence 内の見出し、本文、チェックボックスは例として保持されますが、
状態検証には使われません。

```markdown
# SL-001 質問IDを再抽出後も安定させる

## 背景と根本原因

確認済みの原因を記載します。

## 根拠

`src/example.py:10`

## 受け入れ条件

- [ ] 実行可能な完了条件を記載します

## 対象外

今回扱わない範囲を記載します。

## 実装計画

着手時の計画をリンクします。

## 完了証拠

完了時にコマンドと結果を記録します。
```

`受け入れ条件` で `-`、`*`、`+`、`N.`、`N)` を list item として使う場合、すべてを
非空のチェックボックスにします。`done` では全チェックボックスをチェック済みにします。

`blocked` では次のセクションを追加し、各項目を非空にします。

```markdown
## ブロッカー

- 理由: 外部サービスが停止している
- 解除条件: サービスが復旧する
- 次に確認すること: サービスの稼働状況を確認する
```

`cancelled` では次のセクションを追加します。

```markdown
## 中止理由

代替案を採用したため中止します。
```

`done` から `ready` へ戻す場合は、次のように再オープン理由を本文へ追記します。

```markdown
## 再オープン理由

追加の再現条件が判明したため、対応を再開します。
```

現在の validator は再オープン理由を自動検証しませんが、この追記は運用上必須です。

## Codex の作業手順

1. check と next を実行します。
2. 親ワーカーが課題を選び、in_progress と owner を設定します。
3. 実装ワーカーは担当コードと関連テストだけを変更します。
4. 実装テストとレビューを実行し、実装ワーカーが結果を報告します。
5. 親ワーカーが結果を統合し、受け入れ条件と完了証拠を更新してから done にします。
6. done への更新後に、親ワーカーが render、check、関連テスト、lint を実行します。
7. すべて成功した後にコミットします。
````

- [ ] **Step 3: roadmap と空 backlog を作る**

`roadmap.md` を次の内容で作成する。

```markdown
# SheetLens 改善ロードマップ

マイルストーンは順番を強制するフェーズではありません。着手順は課題の優先度、依存関係、
変更範囲で決定します。

## M1 意味層の整合性

質問、注釈、構造要素の識別子を安定させ、Excel 更新後も意味情報を正しく保持します。

## M2 構造抽出の完全性

Excel に存在する構造と表示意味を、欠落または省略を明示しながら IR へ保存します。

## M3 分析・実行信頼性

質問生成、数式・依存解析、CLI、成果物更新を誤分類や途中状態に強いものにします。

## M4 品質保証

実 xlsm、Windows、再現可能評価、CI、配布検証により本番適用可否を判断可能にします。
```

`backlog.md` は `render_backlog([])` の出力と完全一致させる。

- [ ] **Step 4: ルート指示から管理ワークフローを参照する**

`CLAUDE.md` のコマンド節の後へ次を追加する。

```markdown
## 改善プロジェクト管理

- 継続的な改善課題は `docs/project/README.md` の手順に従う。
- 作業開始時に `uv run python scripts/check_project_state.py check` と `next` を実行する。
- 管理基盤構築と初期課題登録までの bootstrap 期間に限り、親ワーカーが明示的に割り当てた
  管理ファイルの新規作成を実装ワーカーへ委譲できる。
- bootstrap 完了後は、親ワーカーだけが課題の状態、owner、依存関係、`backlog.md` を更新する。
- 実装テストとレビュー後に、親ワーカーが受け入れ条件と完了証拠を更新して課題を `done` にする。
- `done` への更新後に `render`、`check`、関連テスト、lint を実行し、成功後にコミットする。
```

- [ ] **Step 5: 管理基盤と既存リポジトリを全検証する**

Run:

```bash
uv run pytest tests/test_project_state.py -v
uv run python scripts/check_project_state.py check
uv run ruff check .
uv run pytest
```

Expected: project-state tests PASS、check exit 0、Ruff clean、全テスト PASS

- [ ] **Step 6: Task 6 をコミットする**

```bash
git add CLAUDE.md docs/project scripts tests/test_project_state.py
git commit -m "docs: add project management workflow"
```

## Plan Completion Check

- [ ] `docs/superpowers/specs/2026-07-10-sheetlens-project-management-design.md` の正本、状態、並行、CLI、エラー処理、テスト要件へ対応するタスクが存在することを確認する。
- [ ] `rg -n 'T[B]D|T[O]DO|implement[ ]later|fill[ ]in|appropriate[ ]error|similar[ ]to' docs/superpowers/plans/2026-07-10-project-management-foundation.md` が該当なしであることを確認する。
- [ ] `uv run pytest tests/test_project_state.py -v && uv run ruff check . && uv run pytest` を実行する。
- [ ] `git status --short` で意図した変更だけが残っていることを確認する。
