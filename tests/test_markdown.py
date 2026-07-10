from pathlib import Path

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


def test_grid_escapes_newlines_and_pipes():
    sheet = ir.Sheet(
        name="s",
        used_range="A1:B1",
        cells=[ir.Cell(ref="A1", value="行1\n行2"), ir.Cell(ref="B1", value="a|b")],
    )
    md = render_sheet_md(sheet, [], [], [], [])
    grid_lines = [line for line in md.splitlines() if line.startswith("| 1 |")]
    assert grid_lines == ["| 1 | 行1 行2 | a\\|b |"]


def test_validation_with_multiple_ranges_and_empty_ranges_safe():
    ann = SheetAnnotations(
        sheet="s",
        targets=[AnnotationTarget(range="D2", kind="dropdown_semantics", values={"はい": "承認する"})],
    )
    sheet = ir.Sheet(
        name="s",
        used_range="A1:D5",
        cells=[ir.Cell(ref="A1", value="x")],
        validations=[
            ir.ValidationRule(ranges=["C2", "D2"], type="list", choices=["はい", "いいえ"]),
            ir.ValidationRule(ranges=[], type="custom"),
        ],
    )
    md = render_sheet_md(sheet, [], [], [], [], ann)
    assert "承認する" in md  # 2番目の range にも注釈が織り込まれる


def test_multirange_conditional_format_annotation_woven():
    ann = SheetAnnotations(
        sheet="s",
        targets=[AnnotationTarget(range="G1:G9", kind="alert_action", note="担当へ連絡")],
    )
    sheet = ir.Sheet(
        name="s",
        used_range="A1:G9",
        cells=[ir.Cell(ref="A1", value="x")],
        conditional_formats=[
            ir.ConditionalFormat(
                range="F1:F9 G1:G9",
                rule_type="cellIs",
                operator="lessThan",
                formula="0",
            )
        ],
    )
    md = render_sheet_md(sheet, [], [], [], [], ann)
    assert "担当へ連絡" in md


def test_readme_warns_on_gaps():
    wb = ir.Workbook(source_file="a.xlsx", sha256="00" * 32,
                     sheets=[ir.Sheet(name="s")], extraction_gaps=["x の抽出に失敗"])
    md = render_readme(wb, {"s": []}, [], frozenset())
    assert "⚠" in md and "1 件" in md


def test_generated_readme_documents_stable_question_ids():
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[ir.Sheet(name="s")],
    )

    md = render_readme(wb, {"s": []}, [], frozenset())

    assert "`question-ids.json`" in md
    assert "`q2-<rule>-<16hex>`" in md
    assert "旧形式の `q-NNN`" in md
    assert "alias は一度保存した対応先から変更しません" in md
    assert "`annotations/*.yaml` を書き換えません" in md
    assert "回答時点を証明するものではありません" in md
    assert "暗号学的な完全性" in md
    assert "別の有効な過去/現行 ID" in md
    assert "`question-ids.json` を手で編集しないでください" in md


def test_repository_readme_documents_stable_question_ids():
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")

    assert "question-ids.json" in readme
    assert "`q2-<rule>-<16hex>`" in readme
    assert "旧形式の `q-NNN`" in readme
    assert "alias は一度保存した対応先から変更しません" in readme
    assert "`annotations/*.yaml` の質問 ID を書き換えません" in readme
    assert "回答時点を証明するものではありません" in readme
    assert "暗号学的な完全性" in readme
    assert "別の有効な過去/現行 ID" in readme
    assert "`question-ids.json` を手で編集しないでください" in readme
    assert "q2-input_region-<16hex>" in readme
    assert "(q-003)" not in readme


def test_questions_md_checkboxes():
    qs = [Question(id="q-001", sheet="s", target="A1", category="sheet_role", text="役割は？")]
    assert "- [ ] **q-001**" in render_questions_md(qs, frozenset())
    assert "- [x] **q-001**" in render_questions_md(qs, {"q-001"})
