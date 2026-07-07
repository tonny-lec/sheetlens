from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula

from sheetlens.reader.workbook import _formula_text, read_workbook


def _build(wb):
    ws = wb.active
    ws.title = "見積入力"
    ws["A1"] = "見積書"
    ws.merge_cells("A1:C1")
    ws["A3"] = "数量"
    ws["B3"] = 5
    ws["C3"] = "=B3*100"
    ws.column_dimensions["D"].hidden = True
    hidden = wb.create_sheet("計算用")
    hidden["A1"] = 1
    hidden.sheet_state = "hidden"


def test_read_cells_formulas_merges(make_xlsx):
    wb = read_workbook(make_xlsx(_build))
    assert wb.source_file == "test.xlsx"
    assert len(wb.sha256) == 64
    sheet = wb.sheets[0]
    assert sheet.name == "見積入力"
    assert "A1:C1" in sheet.merged
    cells = {c.ref: c for c in sheet.cells}
    assert cells["A1"].value == "見積書"
    assert cells["B3"].value == 5
    assert cells["C3"].formula == "=B3*100"
    assert "D" in sheet.hidden_cols
    assert wb.sheets[1].hidden is True


def test_formula_text_unwraps_known_types():
    assert _formula_text("=A1*2") == "=A1*2"
    assert _formula_text(ArrayFormula("A1:A3", "=SUM(B1:B3)")) == "=SUM(B1:B3)"
    assert _formula_text(DataTableFormula("A1")) is None
