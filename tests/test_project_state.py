from pathlib import Path

from scripts.check_project_state import (
    ProjectItem,
    dependency_closure,
    load_items,
    load_milestones,
    parse_item,
    section_text,
    validate_items,
    validate_milestones,
)


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


def project_item(
    tmp_path: Path,
    item_id: str = "SL-001",
    *,
    status: str = "proposed",
    milestone: str = "M1",
    depends_on: tuple[str, ...] = (),
    touches: tuple[str, ...] = (),
    owner: str | None = None,
    body: str = "",
) -> ProjectItem:
    return ProjectItem(
        path=tmp_path / f"{item_id}.md",
        id=item_id,
        title=item_id,
        status=status,
        priority="P1",
        type="defect",
        milestone=milestone,
        depends_on=depends_on,
        touches=touches,
        owner=owner,
        body=body,
    )


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


def test_load_items_returns_valid_items_in_filename_order(tmp_path: Path) -> None:
    write_item(tmp_path / "SL-002-second.md", valid_front("SL-002"))
    write_item(tmp_path / "SL-001-first.md", valid_front("SL-001"))

    items, issues = load_items(tmp_path)

    assert issues == []
    assert [item.id for item in items] == ["SL-001", "SL-002"]


def test_load_items_reports_unreadable_item_and_continues(tmp_path: Path) -> None:
    unreadable = tmp_path / "SL-001-unreadable.md"
    unreadable.write_bytes(b"\xff\xfe")
    write_item(tmp_path / "SL-002-readable.md", valid_front("SL-002"))

    items, issues = load_items(tmp_path)

    assert [item.id for item in items] == ["SL-002"]
    assert len(issues) == 1
    assert issues[0].path == unreadable
    assert issues[0].message.startswith("課題ファイルを読めません: ")


def test_parse_item_reports_mixed_unknown_keys_in_deterministic_order(tmp_path: Path) -> None:
    path = tmp_path / "SL-001-mixed-keys.md"
    write_item(path, valid_front() + "\nzeta: value\n1: value\nalpha: value")

    item, issues = parse_item(path)

    assert item is None
    assert [issue.message for issue in issues] == [
        "未知の front matter キーです: alpha",
        "未知の front matter キーです: zeta",
        "front matter キーは文字列で指定してください: 1",
    ]


def test_load_items_reports_mixed_unknown_keys_and_continues(tmp_path: Path) -> None:
    invalid = tmp_path / "SL-001-mixed-keys.md"
    write_item(invalid, valid_front() + "\nunknown: value\n1: value")
    write_item(tmp_path / "SL-002-readable.md", valid_front("SL-002"))

    items, issues = load_items(tmp_path)

    assert [item.id for item in items] == ["SL-002"]
    assert [issue.path for issue in issues] == [invalid, invalid]
    assert [issue.message for issue in issues] == [
        "未知の front matter キーです: unknown",
        "front matter キーは文字列で指定してください: 1",
    ]


def test_section_text_returns_trimmed_named_section(tmp_path: Path) -> None:
    item = project_item(
        tmp_path,
        body="""# 課題\r
\r
## 背景と根本原因 \r
  原因を記録する。  \r
\r
### 詳細\r
追加情報\r
\r
## 根拠\r
src/example.py:10\r
""",
    )

    assert section_text(item, "背景と根本原因") == (
        "原因を記録する。  \r\n\r\n### 詳細\r\n追加情報"
    )
    assert section_text(item, "存在しない見出し") == ""


def test_load_milestones_reads_supported_roadmap_headings(tmp_path: Path) -> None:
    roadmap = tmp_path / "roadmap.md"
    roadmap.write_text(
        "# Roadmap\n\n## M1 Foundation\n\n### M2 nested\n\n## M4\n\n## M5 Later\n",
        encoding="utf-8",
    )

    milestones, issues = load_milestones(roadmap)

    assert milestones == {"M1", "M4"}
    assert issues == []


def test_load_milestones_reports_unreadable_roadmap(tmp_path: Path) -> None:
    roadmap = tmp_path / "roadmap.md"
    roadmap.write_bytes(b"\xff\xfe")

    milestones, issues = load_milestones(roadmap)

    assert milestones == set()
    assert len(issues) == 1
    assert issues[0].path == roadmap
    assert issues[0].message.startswith("roadmap.md を読めません: ")


def test_validate_milestones_reports_missing_roadmap_heading(tmp_path: Path) -> None:
    item = project_item(tmp_path, milestone="M2")

    issues = validate_milestones([item], {"M1"})

    assert [issue.message for issue in issues] == [
        "roadmap にマイルストーンがありません: M2"
    ]


def test_dependency_closure_follows_transitive_and_missing_dependencies(
    tmp_path: Path,
) -> None:
    first = project_item(
        tmp_path,
        "SL-001",
        depends_on=("SL-002", "SL-999"),
    )
    second = project_item(tmp_path, "SL-002", depends_on=("SL-003",))
    third = project_item(tmp_path, "SL-003")
    by_id = {item.id: item for item in (first, second, third)}

    assert dependency_closure("SL-001", by_id) == {"SL-002", "SL-003", "SL-999"}
    assert dependency_closure("SL-404", by_id) == set()


def test_validate_items_reports_cycle_and_invalid_done(tmp_path: Path) -> None:
    first = project_item(
        tmp_path,
        "SL-001",
        status="done",
        depends_on=("SL-002",),
        touches=("src/a.py",),
        body=ready_body(),
    )
    second = project_item(
        tmp_path,
        "SL-002",
        status="ready",
        depends_on=("SL-001",),
        touches=("src/b.py",),
        body=ready_body(),
    )

    messages = [issue.message for issue in validate_items([first, second])]

    assert "依存関係が循環しています: SL-001 -> SL-002 -> SL-001" in messages
    assert "done では受け入れ条件をすべてチェックしてください" in messages
    assert "done では完了証拠を記録してください" in messages


def test_validate_items_reports_each_disjoint_cycle(tmp_path: Path) -> None:
    items = [
        project_item(tmp_path, "SL-001", depends_on=("SL-002",)),
        project_item(tmp_path, "SL-002", depends_on=("SL-001",)),
        project_item(tmp_path, "SL-003", depends_on=("SL-004",)),
        project_item(tmp_path, "SL-004", depends_on=("SL-003",)),
    ]

    cycle_messages = [
        issue.message
        for issue in validate_items(items)
        if issue.message.startswith("依存関係が循環しています")
    ]

    assert cycle_messages == [
        "依存関係が循環しています: SL-001 -> SL-002 -> SL-001",
        "依存関係が循環しています: SL-003 -> SL-004 -> SL-003",
    ]


def test_validate_items_reports_duplicate_id_and_missing_dependency(
    tmp_path: Path,
) -> None:
    first = project_item(tmp_path, depends_on=("SL-999",), body=ready_body())
    duplicate = project_item(tmp_path, body=ready_body())

    messages = [issue.message for issue in validate_items([first, duplicate])]

    assert "課題 ID が重複しています: SL-001" in messages
    assert "依存先が存在しません: SL-999" in messages


def test_validate_items_reports_each_required_section(tmp_path: Path) -> None:
    item = project_item(tmp_path)

    messages = [issue.message for issue in validate_items([item])]

    assert messages == [
        "必須セクションがありません: 背景と根本原因",
        "必須セクションがありません: 根拠",
        "必須セクションがありません: 受け入れ条件",
        "必須セクションがありません: 対象外",
        "必須セクションがありません: 実装計画",
        "必須セクションがありません: 完了証拠",
    ]


def test_validate_items_reports_ready_content_and_touches_requirements(
    tmp_path: Path,
) -> None:
    item = project_item(
        tmp_path,
        status="ready",
        body="""## 背景と根本原因

## 根拠

## 受け入れ条件

## 対象外

## 実装計画

## 完了証拠
""",
    )

    messages = [issue.message for issue in validate_items([item])]

    assert messages == [
        "ready では 背景と根本原因 を記載してください",
        "ready では 受け入れ条件 を記載してください",
        "ready では 対象外 を記載してください",
        "ready では touches が必須です",
    ]


def test_validate_items_enforces_owner_status(tmp_path: Path) -> None:
    in_progress = project_item(
        tmp_path,
        "SL-001",
        status="in_progress",
        touches=("src/a.py",),
        body=ready_body(),
    )
    proposed = project_item(
        tmp_path,
        "SL-002",
        owner="agent-a",
        body=ready_body(),
    )

    messages = [issue.message for issue in validate_items([in_progress, proposed])]

    assert messages == [
        "status=in_progress では owner が必須です",
        "owner は in_progress のときだけ設定できます",
    ]


def test_validate_items_reports_missing_blocker_details(tmp_path: Path) -> None:
    item = project_item(
        tmp_path,
        status="blocked",
        touches=("src/a.py",),
        body=ready_body() + "\n## ブロッカー\n- 理由:\n",
    )

    messages = [issue.message for issue in validate_items([item])]

    assert messages == [
        "blocked では 理由 を記載してください",
        "blocked では 解除条件 を記載してください",
        "blocked では 次に確認すること を記載してください",
    ]


def test_validate_items_reports_missing_cancellation_reason(tmp_path: Path) -> None:
    item = project_item(tmp_path, status="cancelled", body=ready_body())

    messages = [issue.message for issue in validate_items([item])]

    assert messages == ["cancelled では中止理由を記載してください"]


def test_validate_items_reports_incomplete_dependency_for_active_item(
    tmp_path: Path,
) -> None:
    dependency = project_item(tmp_path, "SL-001", body=ready_body())
    dependent = project_item(
        tmp_path,
        "SL-002",
        status="ready",
        depends_on=("SL-001",),
        touches=("src/b.py",),
        body=ready_body(),
    )

    messages = [issue.message for issue in validate_items([dependency, dependent])]

    assert "未完了の依存課題があります: SL-001" in messages
