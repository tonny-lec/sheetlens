from sheetlens.detectors.formula_patterns import aggregate_formulas
from sheetlens.detectors.util import runs
from sheetlens.model import ir


def _sheet(cells):
    return ir.Sheet(name="s", cells=cells)


def test_uniform_column_collapses_to_one_pattern():
    cells = [ir.Cell(ref=f"E{r}", formula=f"=C{r}*D{r}") for r in range(11, 31)]
    pats = aggregate_formulas(_sheet(cells))
    assert len(pats) == 1
    assert pats[0].ranges == ["E11:E30"]
    assert pats[0].pattern == "=R[0]C[-2]*R[0]C[-1]"
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
    assert pats[0].pattern == (
        "=VLOOKUP(R[0]C[-2],単価マスタ!R2C1:R9C3,3,FALSE)"
    )


def test_absolute_range_deviation_detected():
    cells = [
        ir.Cell(ref=f"D{r}", formula=f"=VLOOKUP(B{r},$A$2:$C$9,3,0)")
        for r in range(2, 8)
        if r != 5
    ]
    cells.append(ir.Cell(ref="D5", formula="=VLOOKUP(B5,$A$2:$C$5,3,0)"))
    pats = aggregate_formulas(_sheet(cells))
    main = next(p for p in pats if p.exceptions)
    assert main.exceptions == ["D5: =VLOOKUP(B5,$A$2:$C$5,3,0)"]


def test_function_names_and_string_literals_survive():
    cells = [ir.Cell(ref=f"D{r}", formula=f'=LOG10(A{r})+IF(B{r}="AB123",1,0)') for r in (2, 3)]
    pats = aggregate_formulas(_sheet(cells))
    assert len(pats) == 1
    assert pats[0].pattern == '=LOG10(R[0]C[-3])+IF(R[0]C[-2]="AB123",1,0)'


def test_out_of_range_minority_aggregated_into_ranges():
    cells = [ir.Cell(ref=f"E{r}", formula=f"=C{r}*D{r}") for r in range(11, 21)]
    cells += [ir.Cell(ref=f"E{r}", formula=f"=SUM(A{r}:D{r})") for r in (25, 26)]
    pats = aggregate_formulas(_sheet(cells))
    assert len(pats) == 2
    minority = next(p for p in pats if p.pattern == "=SUM(R[0]C[-4]:R[0]C[-1])")
    assert minority.ranges == ["E25:E26"]


def test_runs_empty():
    assert runs([]) == []
