import pytest

from sheetlens.annotations.schema import AnnotationError, find_orphans, load_annotations
from sheetlens.model import ir

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
    assert anns[0].targets[1].values["特急"] == "割増率を自動設定"
    assert anns[0].questions_answered == ["q-001", "q-004"]


def test_invalid_kind_raises_with_filename(tmp_path):
    (tmp_path / "bad.yaml").write_text("sheet: s\ntargets:\n  - kind: unknown_kind\n", encoding="utf-8")
    with pytest.raises(AnnotationError, match="bad.yaml"):
        load_annotations(tmp_path)


def test_malformed_range_reported_not_crash(tmp_path):
    (tmp_path / "a.yaml").write_text(
        "sheet: 見積入力\ntargets:\n  - range: NOTARANGE\n    kind: free_note\n", encoding="utf-8"
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
