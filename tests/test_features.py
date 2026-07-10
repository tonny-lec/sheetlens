from openpyxl.workbook.defined_name import DefinedName
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from sheetlens.reader.workbook import read_workbook


def _add_list_validation(ws, target: str, formula: str) -> None:
    dv = DataValidation(type="list", formula1=formula)
    dv.add(target)
    ws.add_data_validation(dv)


def _rules_by_range(workbook, sheet_name: str = "入力"):
    sheet = next(sheet for sheet in workbook.sheets if sheet.name == sheet_name)
    return {rule.ranges[0]: rule for rule in sheet.validations}


def _build(wb):
    ws = wb.active
    ws.title = "入力"
    master = wb.create_sheet("区分マスタ")
    for i, v in enumerate(["通常", "特急"], start=2):
        master[f"A{i}"] = v
    dv_inline = DataValidation(type="list", formula1='"はい,いいえ"')
    dv_inline.add("B2")
    ws.add_data_validation(dv_inline)
    dv_ref = DataValidation(type="list", formula1="=区分マスタ!$A$2:$A$3")
    dv_ref.add("C5")
    ws.add_data_validation(dv_ref)
    red = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    ws.conditional_formatting.add("F1:F9", CellIsRule(operator="lessThan", formula=["0"], fill=red))


def test_validations_and_conditional_formats(make_xlsx):
    sheet = read_workbook(make_xlsx(_build)).sheets[0]
    rules = {r.ranges[0]: r for r in sheet.validations}
    assert rules["B2"].choices == ["はい", "いいえ"]
    assert rules["C5"].choices == ["通常", "特急"]
    cf = sheet.conditional_formats[0]
    assert cf.range == "F1:F9"
    assert cf.rule_type == "cellIs"
    assert cf.operator == "lessThan"
    assert cf.formula == "0"


def test_resolves_workbook_name_case_insensitively_and_quoted_sheet(make_xlsx):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        master = wb.create_sheet("O'Brien")
        master["A2"] = "通常"
        master["A3"] = "特急"
        wb.defined_names.add(
            DefinedName("Choices", attr_text="'O''Brien'!$A$2:$A$3")
        )
        _add_list_validation(ws, "B2", "=choices")
        _add_list_validation(ws, "C2", "='O''Brien'!$A$2:$A$3")

    workbook = read_workbook(make_xlsx(build))
    rules = _rules_by_range(workbook)
    assert rules["B2"].choices == ["通常", "特急"]
    assert rules["C2"].choices == ["通常", "特急"]
    assert workbook.extraction_gaps == []


def test_resolves_current_sheet_range_and_distinguishes_valid_empty_range(make_xlsx):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        ws["D2"] = "赤"
        ws["D3"] = "青"
        empty = wb.create_sheet("空マスタ")
        wb.defined_names.add(
            DefinedName("EmptyChoices", attr_text="'空マスタ'!$A$1:$A$2")
        )
        _add_list_validation(ws, "B2", "=$D$2:$D$3")
        _add_list_validation(ws, "C2", "=EmptyChoices")

    workbook = read_workbook(make_xlsx(build))
    rules = _rules_by_range(workbook)
    assert rules["B2"].choices == ["赤", "青"]
    assert rules["C2"].choices == []
    assert workbook.extraction_gaps == []
