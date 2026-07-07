from sheetlens.detectors.formula_patterns import aggregate_formulas
from sheetlens.model import ir


def _sheet(cells):
    return ir.Sheet(name="s", cells=cells)


def test_uniform_column_collapses_to_one_pattern():
    cells = [ir.Cell(ref=f"E{r}", formula=f"=C{r}*D{r}") for r in range(11, 31)]
    pats = aggregate_formulas(_sheet(cells))
    assert len(pats) == 1
    assert pats[0].ranges == ["E11:E30"]
    assert pats[0].pattern == "=C{row}*D{row}"
    assert pats[0].example == "=C11*D11"
    assert pats[0].exceptions == []


def test_deviating_cell_inside_range_is_exception():
    cells = [ir.Cell(ref=f"E{r}", formula=f"=C{r}*D{r}") for r in range(11, 31) if r != 15]
    cells.append(ir.Cell(ref="E15", formula="=C15*D15*1.1"))
    pats = aggregate_formulas(_sheet(cells))
    assert len(pats) == 1
    assert pats[0].exceptions == ["E15: =C15*D15*1.1"]
    assert pats[0].ranges == ["E11:E14", "E16:E30"]


def test_absolute_refs_normalized():
    cells = [ir.Cell(ref=f"D{r}", formula=f"=VLOOKUP(B{r},単価マスタ!$A$2:$C$9,3,FALSE)") for r in (2, 3)]
    pats = aggregate_formulas(_sheet(cells))
    assert len(pats) == 1
    assert pats[0].pattern == "=VLOOKUP(B{row},単価マスタ!$A{row}:$C{row},3,FALSE)"
