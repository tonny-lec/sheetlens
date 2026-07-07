import hashlib
from pathlib import Path

import openpyxl

from sheetlens.model import ir
from sheetlens.reader.features import read_conditional_formats, read_validations


def _coerce(value: object) -> ir.Primitive:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)  # datetime 等は文字列化


def _formula_text(raw: object) -> str | None:
    if isinstance(raw, str):
        return raw
    text = getattr(raw, "text", None)
    return text if isinstance(text, str) else None


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
                    cells.append(
                        ir.Cell(
                            ref=c.coordinate,
                            value=_coerce(ws_v[c.coordinate].value),
                            formula=formula,
                        )
                    )
                else:
                    cells.append(ir.Cell(ref=c.coordinate, value=_coerce(c.value)))
        try:
            validations = read_validations(ws_f, wb_v)
        except Exception as e:  # noqa: BLE001 — 欠落は gap として記録して継続
            validations = []
            gaps.append(f"{ws_f.title}: 入力規則の抽出に失敗 ({e})")
        try:
            cformats = read_conditional_formats(ws_f)
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
    return ir.Workbook(
        source_file=path.name,
        sha256=hashlib.sha256(data).hexdigest(),
        sheets=sheets,
        defined_names=defined,
        extraction_gaps=gaps,
    )
