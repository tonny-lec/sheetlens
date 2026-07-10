import errno
import os
from pathlib import Path

import pytest

import scripts.check_project_state as project_state
from scripts.check_project_state import (
    ProjectItem,
    dependency_closure,
    eligible_items,
    load_items,
    load_milestones,
    main,
    parse_item,
    paths_conflict,
    render_backlog,
    run,
    section_text,
    validate_backlog,
    validate_items,
    validate_milestones,
    validate_parallel_work,
    write_backlog,
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
    filename: str | None = None,
    status: str = "proposed",
    milestone: str = "M1",
    depends_on: tuple[str, ...] = (),
    touches: tuple[str, ...] = (),
    owner: str | None = None,
    body: str = "",
) -> ProjectItem:
    return ProjectItem(
        path=tmp_path / (filename or f"{item_id}.md"),
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


def assert_fd_closed(fd: int) -> None:
    try:
        os.fstat(fd)
    except OSError as exc:
        assert exc.errno == errno.EBADF
    else:
        os.close(fd)
        pytest.fail(f"file descriptor remains open: {fd}")


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


def test_section_text_ignores_fenced_h2_and_preserves_fenced_content(
    tmp_path: Path,
) -> None:
    item = project_item(
        tmp_path,
        body=(
            "````python\r\n"
            "## 背景と根本原因\r\n"
            "偽のセクション\r\n"
            "````\r\n"
            "## 背景と根本原因\r\n"
            "実際の原因\r\n"
            "~~~ markdown\r\n"
            "## 根拠\r\n"
            "偽の境界\r\n"
            "~~~~\r\n"
            "原因の続き\r\n"
            "## 根拠\r\n"
            "src/example.py:10\r\n"
        ),
    )

    assert section_text(item, "背景と根本原因") == (
        "実際の原因\r\n"
        "~~~ markdown\r\n"
        "## 根拠\r\n"
        "偽の境界\r\n"
        "~~~~\r\n"
        "原因の続き"
    )
    assert section_text(item, "根拠") == "src/example.py:10"


def test_load_milestones_reads_supported_roadmap_headings(tmp_path: Path) -> None:
    roadmap = tmp_path / "roadmap.md"
    roadmap.write_text(
        "# Roadmap\n\n## M1 Foundation\n\n### M2 nested\n\n## M4\n\n## M5 Later\n",
        encoding="utf-8",
    )

    milestones, issues = load_milestones(roadmap)

    assert milestones == {"M1", "M4"}
    assert issues == []


def test_load_milestones_ignores_headings_inside_fenced_code_blocks(
    tmp_path: Path,
) -> None:
    roadmap = tmp_path / "roadmap.md"
    roadmap.write_text(
        (
            "## M1 Foundation\r\n"
            "````text\r\n"
            "## M2 Fenced\r\n"
            "````\r\n"
            "~~~ roadmap\r\n"
            "## M3 Also fenced\r\n"
            "~~~~\r\n"
            "## M4 Delivery\r\n"
        ),
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


def test_validate_items_rejects_plain_bullet_in_done_acceptance_criteria(
    tmp_path: Path,
) -> None:
    body = ready_body().replace(
        "- [ ] 挙動を修正する",
        "- [x] 挙動を修正する\n- 回帰テストを実行する",
    )
    item = project_item(
        tmp_path,
        status="done",
        touches=("src/a.py",),
        body=body + "pytest: passed\n",
    )

    messages = [issue.message for issue in validate_items([item])]

    assert "done では受け入れ条件をすべてチェックしてください" in messages


@pytest.mark.parametrize("marker", ["-", "*", "+", "1.", "1)"])
def test_validate_items_accepts_checked_done_criterion_for_each_list_marker(
    tmp_path: Path,
    marker: str,
) -> None:
    body = ready_body().replace(
        "- [ ] 挙動を修正する",
        f"{marker} [x] 挙動を修正する",
    )
    item = project_item(
        tmp_path,
        status="done",
        touches=("src/a.py",),
        body=body + "pytest: passed\n",
    )

    messages = [issue.message for issue in validate_items([item])]

    assert "done では受け入れ条件をすべてチェックしてください" not in messages


@pytest.mark.parametrize("plain_marker", ["-", "*", "+", "1.", "1)"])
def test_validate_items_rejects_mixed_plain_done_criterion_for_each_list_marker(
    tmp_path: Path,
    plain_marker: str,
) -> None:
    body = ready_body().replace(
        "- [ ] 挙動を修正する",
        f"- [x] 挙動を修正する\n{plain_marker} 回帰テストを実行する",
    )
    item = project_item(
        tmp_path,
        status="done",
        touches=("src/a.py",),
        body=body + "pytest: passed\n",
    )

    messages = [issue.message for issue in validate_items([item])]

    assert "done では受け入れ条件をすべてチェックしてください" in messages


@pytest.mark.parametrize("empty_marker", ["-", "*", "+", "1.", "1)"])
def test_validate_items_rejects_empty_done_criterion_for_each_list_marker(
    tmp_path: Path,
    empty_marker: str,
) -> None:
    body = ready_body().replace(
        "- [ ] 挙動を修正する",
        f"- [x] 挙動を修正する\n{empty_marker}",
    )
    item = project_item(
        tmp_path,
        status="done",
        touches=("src/a.py",),
        body=body + "pytest: passed\n",
    )

    messages = [issue.message for issue in validate_items([item])]

    assert "done では受け入れ条件をすべてチェックしてください" in messages


def test_validate_items_ignores_fenced_checkbox_for_done(tmp_path: Path) -> None:
    body = ready_body().replace(
        "- [ ] 挙動を修正する",
        "``` markdown\n- [x] example\n```",
    )
    item = project_item(
        tmp_path,
        status="done",
        touches=("src/a.py",),
        body=body + "pytest: passed\n",
    )

    messages = [issue.message for issue in validate_items([item])]

    assert "done では受け入れ条件をすべてチェックしてください" in messages
    assert "- [x] example" in section_text(item, "受け入れ条件")


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


def test_validate_items_cycle_messages_ignore_item_and_edge_order(
    tmp_path: Path,
) -> None:
    forward = [
        project_item(tmp_path, "SL-001", depends_on=("SL-002", "SL-003")),
        project_item(tmp_path, "SL-002", depends_on=("SL-001",)),
        project_item(tmp_path, "SL-003", depends_on=("SL-001",)),
        project_item(tmp_path, "SL-004", depends_on=("SL-005",)),
        project_item(tmp_path, "SL-005", depends_on=("SL-004",)),
    ]
    reversed_items_and_edges = [
        project_item(tmp_path, "SL-005", depends_on=("SL-004",)),
        project_item(tmp_path, "SL-004", depends_on=("SL-005",)),
        project_item(tmp_path, "SL-003", depends_on=("SL-001",)),
        project_item(tmp_path, "SL-002", depends_on=("SL-001",)),
        project_item(tmp_path, "SL-001", depends_on=("SL-003", "SL-002")),
    ]

    def cycle_messages(items: list[ProjectItem]) -> list[str]:
        return [
            issue.message
            for issue in validate_items(items)
            if issue.message.startswith("依存関係が循環しています")
        ]

    expected = [
        "依存関係が循環しています: SL-001 -> SL-002 -> SL-001",
        "依存関係が循環しています: SL-001 -> SL-003 -> SL-001",
        "依存関係が循環しています: SL-004 -> SL-005 -> SL-004",
    ]
    assert cycle_messages(forward) == expected
    assert cycle_messages(reversed_items_and_edges) == expected


def test_validate_items_reports_duplicate_id_and_missing_dependency(
    tmp_path: Path,
) -> None:
    first = project_item(tmp_path, depends_on=("SL-999",), body=ready_body())
    duplicate = project_item(tmp_path, body=ready_body())

    messages = [issue.message for issue in validate_items([first, duplicate])]

    assert "課題 ID が重複しています: SL-001" in messages
    assert "依存先が存在しません: SL-999" in messages


def test_validate_items_excludes_duplicate_ids_from_cycle_graph(tmp_path: Path) -> None:
    first = project_item(
        tmp_path,
        filename="SL-001-first.md",
        body=ready_body(),
    )
    later_with_self_dependency = project_item(
        tmp_path,
        filename="SL-001-later.md",
        depends_on=("SL-001",),
        body=ready_body(),
    )

    issues = validate_items([first, later_with_self_dependency])

    duplicate_issues = [
        issue for issue in issues if issue.message == "課題 ID が重複しています: SL-001"
    ]
    assert [issue.path for issue in duplicate_issues] == [
        first.path,
        later_with_self_dependency.path,
    ]
    assert (
        later_with_self_dependency.path,
        "依存先の課題 ID が重複しています: SL-001",
    ) in [(issue.path, issue.message) for issue in issues]
    assert not any(issue.message.startswith("依存関係が循環しています") for issue in issues)


def test_validate_items_reports_ambiguous_duplicate_dependency_without_status_check(
    tmp_path: Path,
) -> None:
    first = project_item(
        tmp_path,
        filename="SL-001-first.md",
        body=ready_body(),
    )
    second = project_item(
        tmp_path,
        filename="SL-001-second.md",
        body=ready_body(),
    )
    dependent = project_item(
        tmp_path,
        "SL-002",
        status="ready",
        depends_on=("SL-001",),
        touches=("src/dependent.py",),
        body=ready_body(),
    )

    issues = validate_items([first, second, dependent])

    assert (
        dependent.path,
        "依存先の課題 ID が重複しています: SL-001",
    ) in [(issue.path, issue.message) for issue in issues]
    assert not any(issue.message == "未完了の依存課題があります: SL-001" for issue in issues)


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


def test_validate_items_ignores_fenced_blocker_details(tmp_path: Path) -> None:
    item = project_item(
        tmp_path,
        status="blocked",
        touches=("src/a.py",),
        body=(
            ready_body()
            + "\n## ブロッカー\n"
            + "~~~ markdown\n"
            + "- 理由: 外部サービス停止\n"
            + "- 解除条件: サービス復旧\n"
            + "- 次に確認すること: 稼働状況\n"
            + "~~~\n"
        ),
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


def test_parallel_work_rejects_transitive_dependency_and_parent_path(
    tmp_path: Path,
) -> None:
    first = ProjectItem(
        tmp_path / "SL-001-a.md",
        "SL-001",
        "A",
        "in_progress",
        "P1",
        "defect",
        "M1",
        (),
        ("src/sheetlens",),
        "worker-a",
        ready_body(),
    )
    middle = ProjectItem(
        tmp_path / "SL-002-b.md",
        "SL-002",
        "B",
        "done",
        "P1",
        "defect",
        "M1",
        ("SL-001",),
        ("tests/b.py",),
        None,
        ready_body().replace("- [ ]", "- [x]") + "\ncommand: passed\n",
    )
    last = ProjectItem(
        tmp_path / "SL-003-c.md",
        "SL-003",
        "C",
        "in_progress",
        "P1",
        "defect",
        "M1",
        ("SL-002",),
        ("src/sheetlens/reader/a.py",),
        "worker-c",
        ready_body(),
    )

    messages = [
        issue.message for issue in validate_parallel_work([first, middle, last])
    ]
    reversed_messages = [
        issue.message for issue in validate_parallel_work([last, middle, first])
    ]

    assert messages == reversed_messages
    assert "SL-001 と SL-003 は依存関係があるため並行実行できません" in messages
    assert (
        "SL-001 と SL-003 の touches が競合しています: "
        "src/sheetlens <-> src/sheetlens/reader/a.py"
    ) in messages


def test_parallel_work_rejects_duplicate_non_null_owner(tmp_path: Path) -> None:
    first = ProjectItem(
        tmp_path / "SL-001-a.md",
        "SL-001",
        "A",
        "in_progress",
        "P1",
        "defect",
        "M1",
        (),
        ("src/a.py",),
        "worker-a",
        ready_body(),
    )
    second = ProjectItem(
        tmp_path / "SL-002-b.md",
        "SL-002",
        "B",
        "in_progress",
        "P1",
        "defect",
        "M1",
        (),
        ("src/b.py",),
        "worker-a",
        ready_body(),
    )

    messages = [issue.message for issue in validate_parallel_work([second, first])]

    assert messages == ["SL-001 と owner が重複しています: worker-a"]


def test_parallel_work_is_deterministic_and_excludes_duplicate_ids(
    tmp_path: Path,
) -> None:
    duplicate_a = ProjectItem(
        tmp_path / "SL-001-a.md",
        "SL-001",
        "A",
        "in_progress",
        "P1",
        "defect",
        "M1",
        (),
        ("src/a.py",),
        "worker-a",
        ready_body(),
    )
    duplicate_b = ProjectItem(
        tmp_path / "SL-001-b.md",
        "SL-001",
        "B",
        "in_progress",
        "P1",
        "defect",
        "M1",
        ("SL-002",),
        ("src/b.py",),
        "worker-b",
        ready_body(),
    )
    unique = ProjectItem(
        tmp_path / "SL-002.md",
        "SL-002",
        "C",
        "in_progress",
        "P1",
        "defect",
        "M1",
        (),
        ("src/c.py",),
        "worker-c",
        ready_body(),
    )

    forward = validate_parallel_work([duplicate_a, duplicate_b, unique])
    reverse = validate_parallel_work([unique, duplicate_b, duplicate_a])

    assert forward == reverse == []


@pytest.mark.parametrize("root", [".", "/"])
def test_paths_conflict_treats_repository_root_as_parent(root: str) -> None:
    assert paths_conflict(root, "src/a.py")
    assert paths_conflict("src/a.py", root)


def test_paths_conflict_compares_complete_path_components() -> None:
    assert paths_conflict("src/a", "src/a/file.py")
    assert not paths_conflict("src/a", "src/ab/file.py")


def test_parallel_work_sorts_all_touch_conflicts_independent_of_tuple_order(
    tmp_path: Path,
) -> None:
    first = project_item(
        tmp_path,
        "SL-001",
        status="in_progress",
        touches=("src/a/file.py", "src/a"),
        owner="worker-a",
        body=ready_body(),
    )
    second = project_item(
        tmp_path,
        "SL-002",
        status="in_progress",
        touches=("src/a/sub/b.py", "src/a/file.py"),
        owner="worker-b",
        body=ready_body(),
    )
    first_reordered = project_item(
        tmp_path,
        "SL-001",
        status="in_progress",
        touches=tuple(reversed(first.touches)),
        owner="worker-a",
        body=ready_body(),
    )
    second_reordered = project_item(
        tmp_path,
        "SL-002",
        status="in_progress",
        touches=tuple(reversed(second.touches)),
        owner="worker-b",
        body=ready_body(),
    )

    forward = validate_parallel_work([first, second])
    reordered = validate_parallel_work([first_reordered, second_reordered])

    expected_messages = [
        "SL-001 と SL-002 の touches が競合しています: src/a <-> src/a/file.py",
        "SL-001 と SL-002 の touches が競合しています: src/a <-> src/a/sub/b.py",
        "SL-001 と SL-002 の touches が競合しています: "
        "src/a/file.py <-> src/a/file.py",
    ]
    assert forward == reordered
    assert [issue.message for issue in forward] == expected_messages


def test_render_backlog_is_sorted_and_detects_stale_file(tmp_path: Path) -> None:
    low = ProjectItem(
        tmp_path / "SL-002-low.md",
        "SL-002",
        "Low",
        "proposed",
        "P2",
        "quality",
        "M2",
        (),
        (),
        None,
        "",
    )
    high = ProjectItem(
        tmp_path / "SL-001-high.md",
        "SL-001",
        "High",
        "ready",
        "P1",
        "defect",
        "M1",
        (),
        ("src/a.py",),
        None,
        ready_body(),
    )
    backlog = tmp_path / "backlog.md"
    backlog.write_text("stale\n", encoding="utf-8")

    rendered = render_backlog([low, high])
    issues = validate_backlog(backlog, rendered)

    assert rendered.index("SL-001") < rendered.index("SL-002")
    assert "[SL-001](items/SL-001-high.md)" in rendered
    assert [issue.message for issue in issues] == [
        "backlog.md が課題ファイルと同期していません"
    ]
    assert backlog.read_text(encoding="utf-8") == "stale\n"

    write_backlog(backlog, rendered)
    assert backlog.read_text(encoding="utf-8") == rendered


def test_render_backlog_is_deterministic_by_priority_milestone_and_id(
    tmp_path: Path,
) -> None:
    items = [
        ProjectItem(
            tmp_path / "SL-003-third.md",
            "SL-003",
            "Third",
            "proposed",
            "P1",
            "quality",
            "M2",
            (),
            (),
            None,
            "",
        ),
        ProjectItem(
            tmp_path / "SL-002-second.md",
            "SL-002",
            "Second",
            "proposed",
            "P1",
            "quality",
            "M1",
            (),
            (),
            None,
            "",
        ),
        ProjectItem(
            tmp_path / "SL-001-first.md",
            "SL-001",
            "First",
            "proposed",
            "P0",
            "quality",
            "M4",
            (),
            (),
            None,
            "",
        ),
        ProjectItem(
            tmp_path / "SL-004-fourth.md",
            "SL-004",
            "Fourth",
            "proposed",
            "P1",
            "quality",
            "M1",
            (),
            (),
            None,
            "",
        ),
    ]

    forward = render_backlog(items)
    reversed_input = render_backlog(list(reversed(items)))

    assert forward == reversed_input
    assert [forward.index(item_id) for item_id in ("SL-001", "SL-002", "SL-004", "SL-003")] == sorted(
        forward.index(item_id) for item_id in ("SL-001", "SL-002", "SL-004", "SL-003")
    )


def test_write_backlog_preserves_existing_file_and_cleans_temporary_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backlog = tmp_path / "backlog.md"
    backlog.write_text("existing\n", encoding="utf-8")

    def fail_replace(source: Path, target: Path) -> Path:
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        write_backlog(backlog, "replacement\n")

    assert backlog.read_text(encoding="utf-8") == "existing\n"
    assert list(tmp_path.glob(".backlog-*")) == []


def test_validate_backlog_detects_crlf_bytes_as_stale(tmp_path: Path) -> None:
    backlog = tmp_path / "backlog.md"
    expected = "first\nsecond\n"
    backlog.write_bytes(expected.replace("\n", "\r\n").encode("utf-8"))

    assert backlog.read_text(encoding="utf-8") == expected

    issues = validate_backlog(backlog, expected)

    assert [issue.message for issue in issues] == [
        "backlog.md が課題ファイルと同期していません"
    ]


def test_write_backlog_closes_raw_fd_when_fdopen_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backlog = tmp_path / "backlog.md"
    backlog.write_bytes(b"existing\n")
    created: list[tuple[int, str]] = []
    original_mkstemp = project_state.tempfile.mkstemp

    def capture_mkstemp(*, prefix: str, dir: Path, text: bool) -> tuple[int, str]:
        result = original_mkstemp(prefix=prefix, dir=dir, text=text)
        created.append(result)
        return result

    def fail_fdopen(
        fd: int,
        mode: str,
        *,
        encoding: str,
        newline: str,
    ) -> None:
        raise OSError("fdopen failed")

    monkeypatch.setattr(project_state.tempfile, "mkstemp", capture_mkstemp)
    monkeypatch.setattr(project_state.os, "fdopen", fail_fdopen)

    with pytest.raises(OSError, match="fdopen failed"):
        write_backlog(backlog, "replacement\n")

    assert len(created) == 1
    fd, temporary = created[0]
    assert_fd_closed(fd)
    assert backlog.read_bytes() == b"existing\n"
    assert not Path(temporary).exists()


def test_write_backlog_preserves_fdopen_error_when_fd_is_already_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backlog = tmp_path / "backlog.md"
    backlog.write_bytes(b"existing\n")

    def close_fd_and_fail(
        fd: int,
        mode: str,
        *,
        encoding: str,
        newline: str,
    ) -> None:
        os.close(fd)
        raise OSError("fdopen failed after closing fd")

    monkeypatch.setattr(project_state.os, "fdopen", close_fd_and_fail)

    with pytest.raises(OSError, match="fdopen failed after closing fd"):
        write_backlog(backlog, "replacement\n")

    assert backlog.read_bytes() == b"existing\n"
    assert list(tmp_path.glob(".backlog-*")) == []


def test_write_backlog_closes_handle_when_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backlog = tmp_path / "backlog.md"
    backlog.write_bytes(b"existing\n")
    original_fdopen = project_state.os.fdopen
    opened = []
    captured_fds: list[int] = []

    class WriteFailingHandle:
        def __init__(self, handle) -> None:
            self.handle = handle

        def __enter__(self):
            self.handle.__enter__()
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def write(self, text: str) -> int:
            raise OSError("write failed")

    def failing_fdopen(
        fd: int,
        mode: str,
        *,
        encoding: str,
        newline: str,
    ) -> WriteFailingHandle:
        captured_fds.append(fd)
        handle = original_fdopen(
            fd,
            mode,
            encoding=encoding,
            newline=newline,
        )
        opened.append(handle)
        return WriteFailingHandle(handle)

    monkeypatch.setattr(project_state.os, "fdopen", failing_fdopen)

    with pytest.raises(OSError, match="write failed"):
        write_backlog(backlog, "replacement\n")

    assert len(opened) == len(captured_fds) == 1
    assert opened[0].closed
    assert_fd_closed(captured_fds[0])
    assert backlog.read_bytes() == b"existing\n"
    assert list(tmp_path.glob(".backlog-*")) == []


def test_eligible_items_excludes_non_done_missing_and_duplicate_dependencies(
    tmp_path: Path,
) -> None:
    done = ProjectItem(
        tmp_path / "SL-001.md",
        "SL-001",
        "Done",
        "done",
        "P1",
        "defect",
        "M1",
        (),
        ("src/done.py",),
        None,
        ready_body().replace("- [ ]", "- [x]") + "\ncommand: passed\n",
    )
    eligible = ProjectItem(
        tmp_path / "SL-002.md",
        "SL-002",
        "Eligible",
        "ready",
        "P1",
        "defect",
        "M1",
        ("SL-001",),
        ("src/eligible.py",),
        None,
        ready_body(),
    )
    pending = ProjectItem(
        tmp_path / "SL-003.md",
        "SL-003",
        "Pending",
        "proposed",
        "P1",
        "defect",
        "M1",
        (),
        (),
        None,
        ready_body(),
    )
    blocked = ProjectItem(
        tmp_path / "SL-004.md",
        "SL-004",
        "Blocked",
        "ready",
        "P1",
        "defect",
        "M1",
        ("SL-003",),
        ("src/blocked.py",),
        None,
        ready_body(),
    )
    missing = ProjectItem(
        tmp_path / "SL-005.md",
        "SL-005",
        "Missing",
        "ready",
        "P1",
        "defect",
        "M1",
        ("SL-999",),
        ("src/missing.py",),
        None,
        ready_body(),
    )
    duplicate_a = ProjectItem(
        tmp_path / "SL-006-a.md",
        "SL-006",
        "Duplicate A",
        "ready",
        "P1",
        "defect",
        "M1",
        (),
        ("src/a.py",),
        None,
        ready_body(),
    )
    duplicate_b = ProjectItem(
        tmp_path / "SL-006-b.md",
        "SL-006",
        "Duplicate B",
        "ready",
        "P1",
        "defect",
        "M1",
        (),
        ("src/b.py",),
        None,
        ready_body(),
    )
    ambiguous = ProjectItem(
        tmp_path / "SL-007.md",
        "SL-007",
        "Ambiguous",
        "ready",
        "P1",
        "defect",
        "M1",
        ("SL-006",),
        ("src/ambiguous.py",),
        None,
        ready_body(),
    )
    items = [ambiguous, duplicate_b, missing, pending, eligible, done, blocked, duplicate_a]

    assert [item.id for item in eligible_items(items)] == ["SL-002"]
    assert [item.id for item in eligible_items(list(reversed(items)))] == ["SL-002"]


def test_next_returns_only_unblocked_ready_items(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "docs" / "project"
    items_dir = project / "items"
    project.mkdir(parents=True)
    (project / "roadmap.md").write_text("## M1 Test\n## M2 Test\n", encoding="utf-8")
    first_front = valid_front().replace("status: proposed", "status: ready")
    first_front = first_front.replace("touches: []", "touches: [src/a.py]")
    write_item(items_dir / "SL-001-first.md", first_front, ready_body())
    second_front = valid_front("SL-002").replace("depends_on: []", "depends_on: [SL-001]")
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


def test_next_reports_active_conflicts_in_stable_id_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "docs" / "project"
    items_dir = project / "items"
    project.mkdir(parents=True)
    (project / "roadmap.md").write_text("## M1 Test\n", encoding="utf-8")
    candidate = valid_front().replace("status: proposed", "status: ready")
    candidate = candidate.replace(
        "touches: []", "touches: [src/a/file.py, src/b/file.py]"
    )
    write_item(items_dir / "SL-001-candidate.md", candidate, ready_body())
    for item_id, touch in (("SL-006", "src/a"), ("SL-007", "src/b")):
        active = valid_front(item_id).replace("status: proposed", "status: in_progress")
        active = active.replace("touches: []", f"touches: [{touch}]")
        active = active.replace("owner: null", f"owner: worker-{item_id}")
        write_item(items_dir / f"{item_id}-active.md", active, ready_body())
    (project / "backlog.md").write_text("", encoding="utf-8")

    assert run("next", tmp_path) == 0

    assert capsys.readouterr().out.splitlines() == [
        "P1 SL-001 安定質問ID / 競合: SL-006, SL-007"
    ]


def test_next_prints_no_candidates_when_duplicate_state_is_invalid(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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
    assert " / 競合:" not in output


def test_next_collects_all_state_errors_before_candidate_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "docs" / "project"
    items_dir = project / "items"
    project.mkdir(parents=True)
    (project / "roadmap.md").write_text("## M1 Test\n", encoding="utf-8")
    write_item(items_dir / "SL-001-invalid.md", "not: valid")
    first = valid_front("SL-002").replace("status: proposed", "status: in_progress")
    first = first.replace("touches: []", "touches: [src/shared]")
    first = first.replace("owner: null", "owner: worker-a")
    first = first.replace("depends_on: []", "depends_on: [SL-999]")
    write_item(items_dir / "SL-002-first.md", first, ready_body())
    second = valid_front("SL-003").replace("status: proposed", "status: in_progress")
    second = second.replace("milestone: M1", "milestone: M2")
    second = second.replace("touches: []", "touches: [src/shared/file.py]")
    second = second.replace("owner: null", "owner: worker-b")
    write_item(items_dir / "SL-003-second.md", second, ready_body())

    assert run("next", tmp_path) == 1

    output = capsys.readouterr().out
    assert "必須キーがありません: id" in output
    assert "roadmap にマイルストーンがありません: M2" in output
    assert "依存先が存在しません: SL-999" in output
    assert "SL-002 と SL-003 の touches が競合しています" in output
    assert " / 並行可能" not in output
    assert " / 競合:" not in output


def test_check_reports_stale_backlog_and_render_synchronizes_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "docs" / "project"
    items_dir = project / "items"
    project.mkdir(parents=True)
    (project / "roadmap.md").write_text("## M1 Test\n", encoding="utf-8")
    write_item(items_dir / "SL-001-first.md", valid_front(), ready_body())
    backlog = project / "backlog.md"
    backlog.write_text("stale\n", encoding="utf-8")

    assert run("check", tmp_path) == 1
    assert "backlog.md が課題ファイルと同期していません" in capsys.readouterr().out
    assert backlog.read_text(encoding="utf-8") == "stale\n"

    assert run("render", tmp_path) == 0
    assert capsys.readouterr().out == f"生成しました: {backlog}\n"
    assert backlog.read_text(encoding="utf-8") == render_backlog(load_items(items_dir)[0])

    assert run("check", tmp_path) == 0
    assert capsys.readouterr().out == ""


def test_empty_project_commands_are_deterministic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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


def test_render_does_not_mutate_backlog_when_state_is_invalid(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "docs" / "project"
    items_dir = project / "items"
    project.mkdir(parents=True)
    (project / "roadmap.md").write_text("## M1 Test\n", encoding="utf-8")
    duplicate = valid_front()
    write_item(items_dir / "SL-001-a.md", duplicate, ready_body())
    write_item(items_dir / "SL-001-b.md", duplicate, ready_body())
    backlog = project / "backlog.md"
    backlog.write_text("unchanged\n", encoding="utf-8")

    def fail_render(items: list[ProjectItem]) -> str:
        pytest.fail("render_backlog must not run for invalid state")

    monkeypatch.setattr(project_state, "render_backlog", fail_render)

    assert run("render", tmp_path) == 1

    assert "課題 ID が重複しています: SL-001" in capsys.readouterr().out
    assert backlog.read_text(encoding="utf-8") == "unchanged\n"


def test_main_rejects_unknown_command_with_argparse_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["unknown", "--root", str(tmp_path)])

    assert exc_info.value.code == 2
    assert "invalid choice: 'unknown'" in capsys.readouterr().err
