from sheetlens.detectors.regions import detect_regions
from sheetlens.model import ir


def test_bands_split_by_blank_rows():
    # 行 1-3 が連続（空行なし）、行 4-9 が空、行 10-13 が連続 → 2 領域
    cells = [
        ir.Cell(ref="A1", value="見積書"),
        ir.Cell(ref="A2", value="宛先"),
        ir.Cell(ref="B3", value="顧客名"),
    ]
    cells += [ir.Cell(ref="A10", value="品名"), ir.Cell(ref="B10", value="数量")]
    for r in range(11, 14):
        cells += [ir.Cell(ref=f"A{r}", value=f"品{r}"), ir.Cell(ref=f"B{r}", formula=f"=A{r}")]
    regions = detect_regions(ir.Sheet(name="s", cells=cells))
    assert [r.range for r in regions] == ["A1:B3", "A10:B13"]
    assert [r.kind for r in regions] == ["block", "table"]


def test_empty_sheet():
    assert detect_regions(ir.Sheet(name="s")) == []


def test_regions_split_on_blank_columns_and_trim_detached_header():
    cells = [ir.Cell(ref="A1", value="補足")]
    cells += [ir.Cell(ref="C1", value="品名"), ir.Cell(ref="D1", value="数量")]
    for row in range(2, 4):
        cells += [
            ir.Cell(ref=f"C{row}", value=f"品{row}"),
            ir.Cell(ref=f"D{row}", value=row),
        ]

    regions = detect_regions(ir.Sheet(name="s", cells=cells))

    assert [(region.range, region.kind) for region in regions] == [
        ("A1:A1", "block"),
        ("C1:D3", "table"),
    ]


def test_header_note_does_not_bridge_separate_tables_in_the_same_row_band():
    cells = [
        ir.Cell(ref="A1", value="左項目"),
        ir.Cell(ref="B1", value="左値"),
        ir.Cell(ref="C1", value="注記"),
        ir.Cell(ref="D1", value="右項目"),
        ir.Cell(ref="E1", value="右値"),
    ]
    for row in range(2, 4):
        cells += [
            ir.Cell(ref=f"A{row}", value=f"左{row}"),
            ir.Cell(ref=f"B{row}", value=row),
            ir.Cell(ref=f"D{row}", value=f"右{row}"),
            ir.Cell(ref=f"E{row}", value=row),
        ]

    regions = detect_regions(ir.Sheet(name="s", cells=cells))

    assert [region.range for region in regions] == ["A1:B3", "C1:C1", "D1:E3"]
