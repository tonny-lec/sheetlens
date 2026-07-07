from sheetlens.model import ir
from sheetlens.renderers.machine import build_manifest, sheet_dependencies


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


def test_manifest_shape():
    m = build_manifest(_wb())
    assert m["source_file"] == "a.xlsx"
    assert m["sheets"][0] == {"name": "見積入力", "hidden": False, "used_range": "A1:B2"}
    assert m["dependencies"]["見積入力"] == ["単価マスタ"]
    assert m["external_refs"] == ["原価表.xlsx"]
    assert m["extraction_gaps"] == ["gap1"]
    assert m["vba_modules"] == ["Module1.bas"]
