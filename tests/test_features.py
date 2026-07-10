import openpyxl
import pytest
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from sheetlens.reader.features import read_validations
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
        wb.create_sheet("空マスタ")
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


def test_sheet_local_name_shadows_workbook_name_and_other_sheet_falls_back(make_xlsx):
    def build(wb):
        input_ws = wb.active
        input_ws.title = "入力"
        other_ws = wb.create_sheet("別シート")
        master = wb.create_sheet("共通マスタ")
        master["A2"] = "共通1"
        master["A3"] = "共通2"
        input_ws["D2"] = "ローカル1"
        input_ws["D3"] = "ローカル2"
        wb.defined_names.add(
            DefinedName("Choices", attr_text="'共通マスタ'!$A$2:$A$3")
        )
        input_ws.defined_names.add(
            DefinedName("cHoIcEs", attr_text="$D$2:$D$3")
        )
        _add_list_validation(input_ws, "B2", "=CHOICES")
        _add_list_validation(other_ws, "B2", "=choices")

    workbook = read_workbook(make_xlsx(build))
    input_rules = _rules_by_range(workbook, "入力")
    other_rules = _rules_by_range(workbook, "別シート")
    assert input_rules["B2"].choices == ["ローカル1", "ローカル2"]
    assert other_rules["B2"].choices == ["共通1", "共通2"]
    assert workbook.extraction_gaps == []


@pytest.mark.parametrize(
    ("formula", "reason"),
    [
        ("=MissingChoices", "name_not_found"),
        ('=INDIRECT("D2:D3")', "unsupported_indirect"),
        ("=OFFSET(D2,0,0,2,1)", "unsupported_offset"),
        ("=SUM(A1:A2)", "unsupported_reference"),
        (
            "='入力'!$D$2:$D$3,'入力'!$E$2:$E$3",
            "unsupported_reference",
        ),
    ],
)
def test_unresolved_list_source_keeps_rule_and_adds_one_gap(
    make_xlsx, formula, reason
):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        _add_list_validation(ws, "C2", formula)
        dv = DataValidation(type="list", formula1=formula)
        dv.add("D2")
        dv.add("B2")
        ws.add_data_validation(dv)

    workbook = read_workbook(make_xlsx(build))
    sheet = workbook.sheets[0]
    assert len(sheet.validations) == 2
    assert all(rule.formula1 == formula for rule in sheet.validations)
    assert all(rule.choices == [] for rule in sheet.validations)
    assert workbook.extraction_gaps == [
        f"入力: 入力規則 C2 の選択肢を解決できません "
        f"(formula1={formula!r}; reason={reason})",
        f"入力: 入力規則 B2, D2 の選択肢を解決できません "
        f"(formula1={formula!r}; reason={reason})",
    ]


def test_quoted_sheet_name_with_comma_resolves_direct_and_defined_ranges(make_xlsx):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        master = wb.create_sheet("Sales, 2026")
        master["A1"] = "one"
        master["A2"] = "two"
        reference = "'Sales, 2026'!$A$1:$A$2"
        wb.defined_names.add(DefinedName("CommaChoices", attr_text=reference))
        _add_list_validation(ws, "B2", f"={reference}")
        _add_list_validation(ws, "C2", "=CommaChoices")

    workbook = read_workbook(make_xlsx(build))
    rules = _rules_by_range(workbook)
    assert rules["B2"].choices == ["one", "two"]
    assert rules["C2"].choices == ["one", "two"]
    assert workbook.extraction_gaps == []


def test_trailing_text_in_qualified_range_adds_invalid_range_gaps(make_xlsx):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        ws["A1"] = "one"
        ws["A2"] = "two"
        malformed = "'入力'!$A$1:$A$2garbage"
        wb.defined_names.add(DefinedName("TrailingGarbage", attr_text=malformed))
        _add_list_validation(ws, "B2", f"={malformed}")
        _add_list_validation(ws, "C2", "=TrailingGarbage")

    workbook = read_workbook(make_xlsx(build))
    rules = _rules_by_range(workbook)
    assert rules["B2"].choices == []
    assert rules["C2"].choices == []
    assert workbook.extraction_gaps == [
        "入力: 入力規則 B2 の選択肢を解決できません "
        '(formula1="=\'入力\'!$A$1:$A$2garbage"; reason=invalid_range)',
        "入力: 入力規則 C2 の選択肢を解決できません "
        "(formula1='=TrailingGarbage'; reason=invalid_range)",
    ]


@pytest.mark.parametrize(
    ("name", "attr_text", "reason"),
    [
        ("DynamicIndirect", 'INDIRECT("入力!$D$2:$D$3")', "unsupported_indirect"),
        ("DynamicOffset", "OFFSET('入力'!$D$2,0,0,2,1)", "unsupported_offset"),
        ("UnqualifiedGlobal", "$D$2:$D$3", "unsupported_reference"),
        ("MissingSheet", "'存在しない'!$A$1:$A$2", "sheet_not_found"),
        ("BrokenRange", "'入力'!#REF!", "invalid_range"),
        (
            "MultipleAreas",
            "'入力'!$D$2:$D$3,'入力'!$E$2:$E$3",
            "unsupported_reference",
        ),
    ],
)
def test_unsupported_workbook_name_definition_adds_gap(
    make_xlsx, name, attr_text, reason
):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        wb.defined_names.add(DefinedName(name, attr_text=attr_text))
        _add_list_validation(ws, "B2", f"={name}")

    workbook = read_workbook(make_xlsx(build))
    rule = workbook.sheets[0].validations[0]
    assert rule.choices == []
    assert rule.formula1 == f"={name}"
    formula = f"={name}"
    assert workbook.extraction_gaps == [
        "入力: 入力規則 B2 の選択肢を解決できません "
        f"(formula1={formula!r}; reason={reason})"
    ]


def test_invalid_local_name_shadows_valid_workbook_name(make_xlsx):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        master = wb.create_sheet("共通マスタ")
        master["A2"] = "共通1"
        master["A3"] = "共通2"
        wb.defined_names.add(
            DefinedName("Choices", attr_text="'共通マスタ'!$A$2:$A$3")
        )
        ws.defined_names.add(
            DefinedName("choices", attr_text="OFFSET($D$2,0,0,2,1)")
        )
        _add_list_validation(ws, "B2", "=CHOICES")

    workbook = read_workbook(make_xlsx(build))
    assert workbook.sheets[0].validations[0].choices == []
    assert workbook.extraction_gaps[0].endswith("reason=unsupported_offset)")


def test_case_insensitive_duplicate_names_are_ambiguous(make_xlsx):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        first = wb.create_sheet("第一")
        second = wb.create_sheet("第二")
        first["A1"] = "一"
        second["A1"] = "二"
        wb.defined_names.add(
            DefinedName("Choices", attr_text="'第一'!$A$1")
        )
        wb.defined_names.add(
            DefinedName("choices", attr_text="'第二'!$A$1")
        )
        _add_list_validation(ws, "B2", "=CHOICES")

    workbook = read_workbook(make_xlsx(build))
    assert workbook.sheets[0].validations[0].choices == []
    assert workbook.extraction_gaps == [
        "入力: 入力規則 B2 の選択肢を解決できません "
        "(formula1='=CHOICES'; reason=ambiguous_name)"
    ]


def test_read_validations_preserves_old_return_type_and_appends_to_gap_sink(make_xlsx):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        _add_list_validation(ws, "B2", "=MissingChoices")

    path = make_xlsx(build)
    wb_f = openpyxl.load_workbook(path, data_only=False)
    wb_v = openpyxl.load_workbook(path, data_only=True)
    empty_sink: list[str] = []
    existing_sink = ["既存gap"]

    rules = read_validations(
        wb_f["入力"],
        wb_v,
        extraction_gaps=empty_sink,
    )
    read_validations(wb_f["入力"], wb_v, extraction_gaps=existing_sink)
    legacy_rules = read_validations(wb_f["入力"], wb_v)

    assert isinstance(rules, list)
    assert isinstance(legacy_rules, list)
    expected = (
        "入力: 入力規則 B2 の選択肢を解決できません "
        "(formula1='=MissingChoices'; reason=name_not_found)"
    )
    assert empty_sink == [expected]
    assert existing_sink == ["既存gap", expected]
