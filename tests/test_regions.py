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
