from sheetlens.model import ir


def test_cell_display_metadata_roundtrips_and_legacy_input_remains_valid():
    cells = [
        ir.Cell(
            ref="A1",
            value=0.125,
            value_type="number",
            number_format="0.00%",
            display_semantics="percentage",
        ),
        ir.Cell(
            ref="A2",
            value="#DIV/0!",
            value_type="error",
            number_format="General",
            display_semantics="error",
        ),
    ]
    wb = ir.Workbook(
        source_file="display.xlsx",
        sha256="00" * 32,
        sheets=[ir.Sheet(name="Sheet1", cells=cells)],
    )

    restored = ir.Workbook.model_validate_json(wb.model_dump_json())
    legacy = ir.Cell.model_validate({"ref": "B1", "value": 1})

    assert restored == wb
    assert restored.sheets[0].cells[0].model_dump() == {
        "ref": "A1",
        "value": 0.125,
        "formula": None,
        "value_type": "number",
        "number_format": "0.00%",
        "display_semantics": "percentage",
    }
    assert legacy.value_type is None
    assert legacy.number_format is None
    assert legacy.display_semantics is None


def test_conditional_format_migrates_legacy_formula_input():
    constructed = ir.ConditionalFormat(range="A1", rule_type="cellIs", formula="0")
    validated = ir.ConditionalFormat.model_validate(
        {"range": "A1", "rule_type": "cellIs", "formula": "0"}
    )
    empty = ir.ConditionalFormat.model_validate(
        {"range": "A1", "rule_type": "expression", "formula": None}
    )
    preferred = ir.ConditionalFormat.model_validate(
        {
            "range": "A1",
            "rule_type": "expression",
            "formula": "legacy",
            "formulas": ["preferred", "second"],
        }
    )

    assert constructed.formulas == ["0"]
    assert validated.formulas == ["0"]
    assert empty.formulas == []
    assert preferred.formulas == ["preferred", "second"]


def test_conditional_format_formula_compatibility_property_and_dump():
    cf = ir.ConditionalFormat(
        range="A1", rule_type="expression", formulas=["first", "second"]
    )

    assert cf.formula == "first"
    cf.formula = "replacement"
    assert cf.formulas == ["replacement", "second"]
    cf.formula = None
    assert cf.formulas == []
    assert cf.formula is None

    dumped = cf.model_dump()
    assert dumped["formulas"] == []
    assert "formula" not in dumped


def test_conditional_format_payloads_roundtrip_through_workbook_json():
    colors = [
        ir.ConditionalColor(type="rgb", value="FFFF0000", tint=0.0),
        ir.ConditionalColor(type="theme", value=4, tint=0.25),
        ir.ConditionalColor(type="indexed", value=7, tint=-0.1),
        ir.ConditionalColor(type="auto", value=True, tint=0.0),
    ]
    dxf = ir.OoxmlNode(
        tag="dxf",
        attributes={"custom": "1"},
        children=[
            ir.OoxmlNode(
                tag="font",
                children=[ir.OoxmlNode(tag="b", attributes={"val": "1"})],
            )
        ],
    )
    conditional_formats = [
        ir.ConditionalFormat(
            range="A1:A4",
            rule_type="colorScale",
            color_scale=ir.ConditionalColorScale(
                conditions=[
                    ir.ConditionalValue(type="min"),
                    ir.ConditionalValue(type="max", value=10, gte=True),
                ],
                colors=colors,
            ),
            dxf=dxf,
        ),
        ir.ConditionalFormat(
            range="B1:B4",
            rule_type="dataBar",
            data_bar=ir.ConditionalDataBar(
                conditions=[ir.ConditionalValue(type="min"), ir.ConditionalValue(type="max")],
                color=colors[3],
                show_value=False,
                min_length=10,
                max_length=90,
            ),
        ),
        ir.ConditionalFormat(
            range="C1:C4",
            rule_type="iconSet",
            icon_set=ir.ConditionalIconSet(
                icon_style="3TrafficLights1",
                conditions=[ir.ConditionalValue(type="percent", value=33)],
                show_value=True,
                percent=True,
                reverse=False,
            ),
        ),
    ]
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[ir.Sheet(name="Sheet1", conditional_formats=conditional_formats)],
    )

    restored = ir.Workbook.model_validate_json(wb.model_dump_json())

    assert restored == wb
    restored_colors = restored.sheets[0].conditional_formats[0].color_scale.colors
    assert [(color.type, color.value) for color in restored_colors] == [
        ("rgb", "FFFF0000"),
        ("theme", 4),
        ("indexed", 7),
        ("auto", True),
    ]
    assert restored.sheets[0].conditional_formats[0].dxf.children[0].children[0].tag == "b"


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
