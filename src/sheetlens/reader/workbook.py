import hashlib
from pathlib import Path

import openpyxl

from sheetlens.model import ir


def _coerce(value: object) -> ir.Primitive:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)  # datetime 等は文字列化


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
                    formula = raw if isinstance(raw, str) else str(getattr(raw, "text", raw))
                    cells.append(
                        ir.Cell(
                            ref=c.coordinate,
                            value=_coerce(ws_v[c.coordinate].value),
                            formula=formula,
                        )
                    )
                else:
                    cells.append(ir.Cell(ref=c.coordinate, value=_coerce(c.value)))
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
