import hashlib
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

import openpyxl
from openpyxl.cell.cell import Cell as OpenpyxlCell
from openpyxl.styles import numbers

from sheetlens.model import ir
from sheetlens.reader.buttons import extract_buttons
from sheetlens.reader.features import read_conditional_formats, read_validations
from sheetlens.reader.vba import extract_vba


def _coerce(value: object) -> ir.Primitive:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)  # datetime 等は文字列化


def _formula_text(raw: object) -> str | None:
    if isinstance(raw, str):
        return raw
    text = getattr(raw, "text", None)
    return text if isinstance(text, str) else None


def _datetime_format_semantics(number_format: str) -> ir.CellDisplaySemantics | None:
    normalized_format = number_format.lower()
    if numbers.is_timedelta_format(normalized_format):
        return "duration"
    semantic = numbers.is_datetime(normalized_format)
    if semantic in ("date", "time", "datetime"):
        return semantic
    return None


def _datetime_value_type(value: object, number_format: str) -> ir.CellValueType | None:
    if not isinstance(value, (datetime, date, time, timedelta)):
        return None
    semantic = _datetime_format_semantics(number_format)
    if semantic is not None:
        return semantic
    if isinstance(value, timedelta):
        return "duration"
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    return "time"


def _active_format_text(number_format: str) -> str:
    active: list[str] = []
    in_quote = False
    index = 0
    while index < len(number_format):
        char = number_format[index]
        if char == '"':
            in_quote = not in_quote
            index += 1
            continue
        if in_quote:
            index += 1
            continue
        if char in ("\\", "_", "*"):
            index += 2
            continue
        active.append(char)
        index += 1
    return "".join(active)


def _has_currency_format(number_format: str) -> bool:
    if re.search(r"\[\$(?!-)[^\]]+\]", number_format):
        return True
    without_brackets = re.sub(r"\[[^\]]*\]", "", number_format)
    return any(symbol in without_brackets for symbol in ("$", "¥", "￥", "€", "£"))


def _has_leading_zero_format(number_format: str) -> bool:
    active = _active_format_text(number_format).split(";", 1)[0]
    active = re.sub(r"\[[^\]]*\]", "", active)
    if "/" in active or re.search(r"[Ee][+-]?0", active):
        return False
    integer_part = active.split(".", 1)[0]
    return re.search(r"0{2,}", integer_part) is not None


def _value_type(
    cell: OpenpyxlCell,
    value: object,
    number_format: str,
) -> ir.CellValueType | None:
    if value is None:
        return None
    if cell.data_type == "e":
        return "error"
    datetime_value_type = _datetime_value_type(value, number_format)
    if datetime_value_type is not None:
        return datetime_value_type
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return None


def _display_semantics(
    value_type: ir.CellValueType | None,
    value: object,
    number_format: str,
) -> ir.CellDisplaySemantics | None:
    if value_type in ("error", "date", "time", "datetime", "duration"):
        return value_type
    if value_type == "string" and isinstance(value, str) and re.fullmatch(r"0\d+", value):
        return "leading_zero"
    if value_type not in ("number", None):
        return None
    datetime_semantics = _datetime_format_semantics(number_format)
    if datetime_semantics is not None:
        return datetime_semantics
    active_format = _active_format_text(number_format)
    if "%" in active_format:
        return "percentage"
    if _has_currency_format(number_format):
        return "currency"
    if _has_leading_zero_format(number_format):
        return "leading_zero"
    return None


def _read_cell(formula_cell: OpenpyxlCell, value_cell: OpenpyxlCell) -> ir.Cell:
    is_formula = formula_cell.data_type == "f"
    raw_value = value_cell.value if is_formula else formula_cell.value
    metadata_cell = value_cell if is_formula else formula_cell
    number_format = formula_cell.number_format
    value_type = _value_type(metadata_cell, raw_value, number_format)
    return ir.Cell(
        ref=formula_cell.coordinate,
        value=_coerce(raw_value),
        formula=_formula_text(formula_cell.value) if is_formula else None,
        value_type=value_type,
        number_format=number_format,
        display_semantics=_display_semantics(value_type, raw_value, number_format),
    )


def read_workbook(path: Path) -> ir.Workbook:
    data = path.read_bytes()
    keep_vba = path.suffix.lower() in (".xlsm", ".xltm")
    wb_f = openpyxl.load_workbook(path, data_only=False, keep_vba=keep_vba)
    wb_v = openpyxl.load_workbook(path, data_only=True)
    gaps: list[str] = []
    sheets: list[ir.Sheet] = []
    for ws_f in wb_f.worksheets:
        ws_v = wb_v[ws_f.title]
        cells: list[ir.Cell] = []
        for row in ws_f.iter_rows():
            for c in row:
                if c.value is None:
                    continue
                if c.data_type == "f":
                    raw = c.value
                    formula = _formula_text(raw)
                    if formula is None:
                        gaps.append(
                            f"{ws_f.title}!{c.coordinate}: 未対応の数式型 "
                            f"{type(raw).__name__} のため数式を抽出できませんでした"
                        )
                cells.append(_read_cell(c, ws_v[c.coordinate]))
        try:
            validations = read_validations(
                ws_f,
                wb_v,
                extraction_gaps=gaps,
            )
        except Exception as e:  # noqa: BLE001 — 欠落は gap として記録して継続
            validations = []
            gaps.append(f"{ws_f.title}: 入力規則の抽出に失敗 ({e})")
        try:
            cformats = read_conditional_formats(ws_f, extraction_gaps=gaps)
        except Exception as e:  # noqa: BLE001
            cformats = []
            gaps.append(f"{ws_f.title}: 条件付き書式の抽出に失敗 ({e})")
        sheets.append(
            ir.Sheet(
                name=ws_f.title,
                used_range=ws_f.calculate_dimension() if cells else None,
                hidden=ws_f.sheet_state != "visible",
                protected=bool(ws_f.protection.sheet),
                hidden_cols=sorted(k for k, v in ws_f.column_dimensions.items() if v.hidden),
                hidden_rows=sorted(k for k, v in ws_f.row_dimensions.items() if v.hidden),
                cells=cells,
                merged=[str(r) for r in ws_f.merged_cells.ranges],
                validations=validations,
                conditional_formats=cformats,
            )
        )
    defined = {}
    for name, defn in wb_f.defined_names.items():
        defined[name] = defn.attr_text or ""
    vba_modules: list[ir.VbaModule] = []
    buttons: list[ir.ButtonLink] = []
    try:
        vba_modules = extract_vba(path)
    except Exception as e:  # noqa: BLE001
        gaps.append(f"VBA の抽出に失敗 ({e})")
    try:
        buttons = extract_buttons(path)
    except Exception as e:  # noqa: BLE001
        gaps.append(f"ボタン↔マクロ対応の抽出に失敗 ({e})")
    return ir.Workbook(
        source_file=path.name,
        sha256=hashlib.sha256(data).hexdigest(),
        sheets=sheets,
        vba_modules=vba_modules,
        buttons=buttons,
        defined_names=defined,
        extraction_gaps=gaps,
    )
