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
