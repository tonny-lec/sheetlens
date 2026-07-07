from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from sheetlens.reader.workbook import read_workbook


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
