import pytest

from sheetlens.annotations.schema import (
    AnnotationError,
    DropdownSemanticsTarget,
    InputSourceTarget,
    find_orphans,
    load_annotations,
)
from sheetlens.model import ir
from sheetlens.pipeline import analyze, find_unwoven

VALID_YAML = """\
sheet: 見積入力
role: "営業担当のメイン入力画面"
workflow_stage: "見積提示フェーズ"
targets:
  - range: A10:H30
    kind: input_source
    value: manual
    by: "営業担当"
  - range: C5
    kind: dropdown_semantics
    values:
      通常: "標準納期を適用"
      特急: "割増率を自動設定"
questions_answered: [q-001, q-004]
"""


def _wb():
    return ir.Workbook(
        source_file="a.xlsx", sha256="00" * 32,
        sheets=[ir.Sheet(name="見積入力", used_range="A1:H30")],
    )


def test_load_valid(tmp_path):
    (tmp_path / "見積入力.yaml").write_text(VALID_YAML, encoding="utf-8")
    anns = load_annotations(tmp_path)
    assert anns[0].sheet == "見積入力"
    assert isinstance(anns[0].targets[0], InputSourceTarget)
    assert isinstance(anns[0].targets[1], DropdownSemanticsTarget)
    assert anns[0].targets[1].values["特急"] == "割増率を自動設定"
    assert anns[0].questions_answered == ["q-001", "q-004"]


@pytest.mark.parametrize(
    "target",
    [
        "kind: input_source\n    range: A1",
        "kind: dropdown_semantics\n    range: A1\n    values: {}",
        "kind: trigger_timing\n    range: Module1.Run",
        "kind: alert_action\n    range: A1",
        "kind: free_note\n    range: A1",
        "kind: hidden_reason",
        "kind: sheet_role",
        "kind: sheet_role\n    range: A1",
        "kind: input_source\n    range: A1\n    value: manual\n    values: {}",
    ],
)
def test_kind_specific_empty_or_missing_content_is_rejected(tmp_path, target):
    (tmp_path / "bad.yaml").write_text(
        f"sheet: s\ntargets:\n  - {target.replace(chr(10), chr(10) + '    ')}\n",
        encoding="utf-8",
    )
    with pytest.raises(AnnotationError, match="bad.yaml"):
        load_annotations(tmp_path)


def test_invalid_kind_raises_with_filename(tmp_path):
    (tmp_path / "bad.yaml").write_text("sheet: s\ntargets:\n  - kind: unknown_kind\n", encoding="utf-8")
    with pytest.raises(AnnotationError, match="bad.yaml"):
        load_annotations(tmp_path)


def test_duplicate_sheet_annotations_are_rejected_with_both_filenames(tmp_path):
    (tmp_path / "first.yaml").write_text("sheet: s\n", encoding="utf-8")
    (tmp_path / "second.yaml").write_text("sheet: s\n", encoding="utf-8")

    with pytest.raises(AnnotationError, match=r"second\.yaml.*first\.yaml"):
        load_annotations(tmp_path)


def test_malformed_range_reported_not_crash(tmp_path):
    (tmp_path / "a.yaml").write_text(
        "sheet: 見積入力\ntargets:\n  - range: NOTARANGE\n    kind: free_note\n    note: test\n", encoding="utf-8"
    )
    orphans = find_orphans(_wb(), load_annotations(tmp_path))
    assert any("NOTARANGE" in o and "不正" in o for o in orphans)


def test_unknown_key_rejected(tmp_path):
    (tmp_path / "typo.yaml").write_text(
        "sheet: s\ntargets:\n  - kind: free_note\n    vlaue: oops\n", encoding="utf-8"
    )
    with pytest.raises(AnnotationError, match="typo.yaml"):
        load_annotations(tmp_path)


def test_orphan_detection(tmp_path):
    (tmp_path / "見積入力.yaml").write_text(VALID_YAML, encoding="utf-8")
    (tmp_path / "消えたシート.yaml").write_text("sheet: 消えたシート\n", encoding="utf-8")
    wb = _wb()
    wb.sheets[0].used_range = "A1:F20"  # A10:H30 が範囲外になる
    orphans = find_orphans(wb, load_annotations(tmp_path))
    assert any("消えたシート" in o for o in orphans)
    assert any("A10:H30" in o for o in orphans)
    assert not any("C5" in o for o in orphans)


def test_structural_range_allows_annotation_outside_content_range(tmp_path):
    (tmp_path / "見積入力.yaml").write_text(
        "sheet: 見積入力\ntargets:\n  - range: H20:H30\n    kind: free_note\n    note: test\n",
        encoding="utf-8",
    )
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="見積入力",
                content_range="A1:F20",
                structural_range="A1:H30",
            )
        ],
    )

    assert find_orphans(wb, load_annotations(tmp_path)) == []


def test_legacy_used_range_assignment_updates_annotation_boundary(tmp_path):
    (tmp_path / "見積入力.yaml").write_text(
        "sheet: 見積入力\ntargets:\n  - range: G21:H30\n    kind: free_note\n    note: test\n",
        encoding="utf-8",
    )
    wb = _wb()

    wb.sheets[0].used_range = "A1:F20"

    orphans = find_orphans(wb, load_annotations(tmp_path))
    assert orphans == ["見積入力!G21:H30: 現在の構造範囲 A1:F20 の外にあります"]


def test_vba_annotation_sheet_is_not_reported_as_missing(tmp_path):
    (tmp_path / "vba.yaml").write_text(
        "sheet: (VBA)\ntargets:\n"
        "  - kind: trigger_timing\n"
        "    range: ThisWorkbook.cls.Workbook_Open\n"
        "    when: 起動時\n",
        encoding="utf-8",
    )

    assert find_orphans(_wb(), load_annotations(tmp_path)) == []


def test_vba_event_annotation_is_checked_against_vba_questions(tmp_path):
    (tmp_path / "vba.yaml").write_text(
        "sheet: (VBA)\ntargets:\n"
        "  - kind: trigger_timing\n"
        "    range: ThisWorkbook.cls.Workbook_Open\n"
        "    when: 起動時\n",
        encoding="utf-8",
    )
    wb = ir.Workbook(
        source_file="a.xlsm",
        sha256="00" * 32,
        vba_modules=[
            ir.VbaModule(
                name="ThisWorkbook.cls",
                code="Private Sub Workbook_Open()\nEnd Sub",
            )
        ],
    )
    annotations = load_annotations(tmp_path)

    assert find_unwoven(wb, analyze(wb), annotations) == []
