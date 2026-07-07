from sheetlens.model import ir


def test_workbook_json_roundtrip():
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="見積入力",
                used_range="A1:C3",
                cells=[ir.Cell(ref="A1", value="見積書"), ir.Cell(ref="C3", formula="=A1*2")],
                merged=["A1:B1"],
                validations=[
                    ir.ValidationRule(ranges=["C5"], type="list", formula1='"通常,特急"', choices=["通常", "特急"])
                ],
                conditional_formats=[
                    ir.ConditionalFormat(range="F1:F9", rule_type="cellIs", operator="lessThan", formula="0")
                ],
            )
        ],
        vba_modules=[ir.VbaModule(name="Module1", code="Sub X()\nEnd Sub")],
        buttons=[ir.ButtonLink(sheet="見積入力", macro="Module1.X")],
        extraction_gaps=["dummy gap"],
    )
    restored = ir.Workbook.model_validate_json(wb.model_dump_json())
    assert restored == wb
    assert restored.sheets[0].cells[1].formula == "=A1*2"
