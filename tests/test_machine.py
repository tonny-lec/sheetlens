from sheetlens.model import ir
from sheetlens.renderers.machine import build_manifest, external_references, sheet_dependencies


def _wb():
    return ir.Workbook(
        source_file="a.xlsx", sha256="00" * 32,
        sheets=[
            ir.Sheet(name="見積入力", used_range="A1:B2",
                     cells=[ir.Cell(ref="A1", formula="=VLOOKUP(B1,単価マスタ!A:C,3,0)"),
                            ir.Cell(ref="B2", formula="=[原価表.xlsx]原価!B2")]),
            ir.Sheet(name="単価マスタ", used_range="A1:C9", cells=[ir.Cell(ref="A1", value="品名")]),
        ],
        vba_modules=[ir.VbaModule(name="Module1.bas", code="")],
        extraction_gaps=["gap1"],
    )


def test_dependencies():
    assert sheet_dependencies(_wb()) == {"見積入力": ["単価マスタ"], "単価マスタ": []}


def test_dependencies_no_substring_false_positive():
    a1_only = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="入力",
                cells=[ir.Cell(ref="A1", formula="=VLOOKUP(B1,単価マスタ!A:C,3,0)")],
            ),
            ir.Sheet(name="単価マスタ"),
            ir.Sheet(name="マスタ"),
        ],
    )
    assert sheet_dependencies(a1_only) == {"入力": ["単価マスタ"], "単価マスタ": [], "マスタ": []}

    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="入力",
                cells=[
                    ir.Cell(ref="A1", formula="=VLOOKUP(B1,単価マスタ!A:C,3,0)"),
                    ir.Cell(ref="A2", formula="=マスタ!B2"),
                ],
            ),
            ir.Sheet(name="単価マスタ"),
            ir.Sheet(name="マスタ"),
        ],
    )
    assert sheet_dependencies(wb) == {"入力": ["マスタ", "単価マスタ"], "単価マスタ": [], "マスタ": []}


def test_dependencies_include_validation_and_cf():
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="入力",
                validations=[
                    ir.ValidationRule(
                        ranges=["B5"],
                        type="list",
                        formula1="=区分マスタ!$A$2:$A$3",
                    )
                ],
                conditional_formats=[
                    ir.ConditionalFormat(
                        range="F1:F9",
                        rule_type="expression",
                        formula="判定!$A$1>0",
                    )
                ],
            ),
            ir.Sheet(name="区分マスタ"),
            ir.Sheet(name="判定"),
        ],
    )
    assert sheet_dependencies(wb)["入力"] == ["判定", "区分マスタ"]


def test_external_references_index_form():
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[ir.Sheet(name="s", cells=[ir.Cell(ref="A1", formula="=[1]原価!B2")])],
    )
    assert external_references(wb) == ["外部ブック[1]（インデックス形式・未解決）"]


def test_manifest_shape():
    m = build_manifest(_wb())
    assert m["source_file"] == "a.xlsx"
    assert m["sheets"][0] == {"name": "見積入力", "hidden": False, "used_range": "A1:B2"}
    assert m["dependencies"]["見積入力"] == ["単価マスタ"]
    assert m["external_refs"] == ["原価表.xlsx"]
    assert m["extraction_gaps"] == ["gap1"]
    assert m["vba_modules"] == ["Module1.bas"]
