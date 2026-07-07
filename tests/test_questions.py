from sheetlens.detectors.questions import generate_questions
from sheetlens.detectors.regions import Region
from sheetlens.model import ir


def test_rules_produce_expected_categories():
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="入力",
                used_range="A1:F30",
                hidden_cols=["D"],
                cells=[ir.Cell(ref="A3", value="顧客名"), ir.Cell(ref="E11", formula="=C11*D11")],
                validations=[ir.ValidationRule(ranges=["C5"], type="list", choices=["通常", "特急"])],
                conditional_formats=[ir.ConditionalFormat(range="F11:F30", rule_type="cellIs", operator="lessThan", formula="0")],
            )
        ],
        vba_modules=[ir.VbaModule(name="Sheet1.cls", code="Private Sub Worksheet_Change(ByVal Target As Range)\nEnd Sub")],
        buttons=[ir.ButtonLink(sheet="入力", macro="Module1.Register")],
    )
    regions = {"入力": [Region(range="A3:B8", kind="block"), Region(range="A10:F30", kind="table")]}
    qs = generate_questions(wb, regions, {"入力": []})
    cats = {q.category for q in qs}
    assert cats == {"sheet_role", "input_source", "dropdown_semantics", "alert_action", "trigger_timing", "hidden_reason"}
    assert [q.id for q in qs] == [f"q-{i:03d}" for i in range(1, len(qs) + 1)]
    # A3:B8 は数式を含まないので input_source、A10:F30 は E11 の数式を含むので対象外
    targets = [q.target for q in qs if q.category == "input_source"]
    assert targets == ["A3:B8"]
