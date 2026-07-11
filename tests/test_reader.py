from datetime import date, datetime, time, timedelta

from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula

from sheetlens.reader.workbook import (
    _formula_text,
    _has_currency_format,
    _has_leading_zero_format,
    read_workbook,
)


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


def test_bounded_currency_and_leading_zero_format_classification():
    assert _has_currency_format("[$USD] #,##0.00") is True
    assert _has_currency_format("[$USD-409] #,##0.00") is True
    assert _has_currency_format("[$-409]0.00") is False
    assert _has_leading_zero_format("00000") is True
    assert _has_leading_zero_format("000-000") is True
    assert _has_leading_zero_format("0/00") is False
    assert _has_leading_zero_format("00E+00") is False
    assert _has_leading_zero_format("0 0") is False


def _build_display_semantics(wb):
    ws = wb.active
    ws["A1"] = 0.125
    ws["A1"].number_format = "0.00%"
    ws["A2"] = 1234.5
    ws["A2"].number_format = "¥#,##0.00"
    ws["A3"] = date(2026, 7, 11)
    ws["A3"].number_format = "yyyy-mm-dd"
    ws["A4"] = time(14, 30, 5)
    ws["A4"].number_format = "hh:mm:ss"
    ws["A5"] = datetime(2026, 7, 11, 14, 30, 5)
    ws["A5"].number_format = "yyyy-mm-dd hh:mm:ss"
    ws["A6"] = timedelta(hours=27, minutes=5)
    ws["A6"].number_format = "[h]:mm:ss"
    ws["A7"] = 123
    ws["A7"].number_format = "00000"
    ws["A8"] = "00123"
    ws["A9"] = "#DIV/0!"
    ws["A10"] = "=1/0"
    ws["A11"] = 12.5
    ws["A11"].number_format = '"%"0.00'
    ws["A12"] = 12.5
    ws["A12"].number_format = r"\%0.00"
    ws["A13"] = "=1/4"
    ws["A13"].number_format = "0.00%"
    ws["A14"] = "=1000"
    ws["A14"].number_format = "$#,##0"
    ws["A15"] = "=DATE(2026,7,11)"
    ws["A15"].number_format = "yyyy-mm-dd"
    ws["A16"] = "=123"
    ws["A16"].number_format = "00000"
    ws["A17"] = date(2026, 7, 11)
    ws["A17"].number_format = "YYYY-MM-DD"


def test_read_cell_types_number_formats_and_display_semantics(make_xlsx):
    wb = read_workbook(make_xlsx(_build_display_semantics))
    restored = type(wb).model_validate_json(wb.model_dump_json())
    cells = {cell.ref: cell for cell in restored.sheets[0].cells}

    assert (cells["A1"].value_type, cells["A1"].number_format, cells["A1"].display_semantics) == (
        "number",
        "0.00%",
        "percentage",
    )
    assert (cells["A2"].value_type, cells["A2"].display_semantics) == ("number", "currency")
    assert (cells["A3"].value_type, cells["A3"].display_semantics) == ("date", "date")
    assert (cells["A4"].value_type, cells["A4"].display_semantics) == ("time", "time")
    assert (cells["A5"].value_type, cells["A5"].display_semantics) == (
        "datetime",
        "datetime",
    )
    assert (cells["A6"].value_type, cells["A6"].display_semantics) == (
        "duration",
        "duration",
    )
    assert (cells["A7"].value_type, cells["A7"].display_semantics) == (
        "number",
        "leading_zero",
    )
    assert (cells["A8"].value_type, cells["A8"].display_semantics) == (
        "string",
        "leading_zero",
    )
    assert (cells["A9"].value_type, cells["A9"].display_semantics) == ("error", "error")
    assert cells["A10"].formula == "=1/0"
    assert cells["A10"].value is None
    assert cells["A10"].value_type is None
    assert cells["A10"].number_format == "General"
    assert cells["A10"].display_semantics is None
    assert cells["A11"].display_semantics is None
    assert cells["A12"].display_semantics is None
    assert cells["A13"].value_type is None
    assert cells["A13"].display_semantics == "percentage"
    assert cells["A14"].display_semantics == "currency"
    assert cells["A15"].display_semantics == "date"
    assert cells["A16"].display_semantics == "leading_zero"
    assert (cells["A17"].value_type, cells["A17"].display_semantics) == ("date", "date")
