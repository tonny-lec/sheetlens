from sheetlens.annotations.schema import AnnotationTarget, SheetAnnotations
from sheetlens.detectors.formula_patterns import FormulaPattern
from sheetlens.detectors.questions import Question
from sheetlens.detectors.regions import Region
from sheetlens.model import ir
from sheetlens.renderers.markdown import render_questions_md, render_readme, render_sheet_md


def _sheet():
    return ir.Sheet(
        name="見積入力",
        used_range="A1:E12",
        cells=[
            ir.Cell(ref="A1", value="見積書"),
            ir.Cell(ref="A3", value="顧客名"),
            ir.Cell(ref="E11", value=None, formula="=C11*D11"),
        ],
        merged=["A1:C1"],
        validations=[ir.ValidationRule(ranges=["C5"], type="list", choices=["通常", "特急"])],
        conditional_formats=[
            ir.ConditionalFormat(range="F11:F30", rule_type="cellIs", operator="lessThan", formula="0")
        ],
    )


def test_sheet_md_mentions_structure():
    md = render_sheet_md(
        _sheet(),
        [FormulaPattern(ranges=["E11:E30"], pattern="=C{row}*D{row}", example="=C11*D11",
                        exceptions=["E15: =C15*D15*1.1"])],
        [Region(range="A3:B8", kind="block")],
        [],
        [ir.ButtonLink(sheet="見積入力", macro="Module1.Register")],
    )
    assert "# シート: 見積入力" in md
    assert "[A1:C1 結合]" in md
    assert "E11:E30" in md and "=C{row}*D{row}" in md
    assert "E15: =C15*D15*1.1" in md  # 例外の強調
    assert "通常" in md and "特急" in md
    assert "lessThan 0" in md
    assert "Module1.Register" in md


def test_annotations_and_unanswered_woven_in():
    ann = SheetAnnotations(
        sheet="見積入力", role="営業のメイン入力画面",
        targets=[AnnotationTarget(range="A3:B8", kind="input_source", value="manual", by="営業担当")],
    )
    qs = [Question(id="q-001", sheet="見積入力", target="A3:B8", category="input_source", text="誰が入力？")]
    md = render_sheet_md(_sheet(), [], [Region(range="A3:B8", kind="block")], qs, [], ann, frozenset())
    assert "💬 業務上の意味" in md and "営業担当" in md and "営業のメイン入力画面" in md
    assert "❓ 未確認" in md and "q-001" in md
    md_answered = render_sheet_md(_sheet(), [], [Region(range="A3:B8", kind="block")], qs, [], ann, {"q-001"})
    assert "q-001" not in md_answered


def test_readme_warns_on_gaps():
    wb = ir.Workbook(source_file="a.xlsx", sha256="00" * 32,
                     sheets=[ir.Sheet(name="s")], extraction_gaps=["x の抽出に失敗"])
    md = render_readme(wb, {"s": []}, [], frozenset())
    assert "⚠" in md and "1 件" in md


def test_questions_md_checkboxes():
    qs = [Question(id="q-001", sheet="s", target="A1", category="sheet_role", text="役割は？")]
    assert "- [ ] **q-001**" in render_questions_md(qs, frozenset())
    assert "- [x] **q-001**" in render_questions_md(qs, {"q-001"})
