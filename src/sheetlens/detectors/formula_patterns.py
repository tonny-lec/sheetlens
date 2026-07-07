import re
from collections import defaultdict

from openpyxl.utils import coordinate_to_tuple, get_column_letter
from pydantic import BaseModel, Field

from sheetlens.detectors.util import runs
from sheetlens.model import ir

_STRING_RE = re.compile(r'("(?:[^"]|"")*")')
_ROW_RE = re.compile(r"(?<![A-Za-z0-9_$])(\$?[A-Z]{1,3})\$?\d+(?![\w(])")


class FormulaPattern(BaseModel):
    ranges: list[str]
    pattern: str
    example: str
    exceptions: list[str] = Field(default_factory=list)


def _normalize(formula: str) -> str:
    parts = _STRING_RE.split(formula)
    for i in range(0, len(parts), 2):  # 偶数インデックスのみ（文字列リテラルの外側）
        parts[i] = _ROW_RE.sub(lambda m: m.group(1) + "{row}", parts[i])
    return "".join(parts)


def aggregate_formulas(sheet: ir.Sheet) -> list[FormulaPattern]:
    by_col: dict[str, list[tuple[int, ir.Cell]]] = defaultdict(list)
    for cell in sheet.cells:
        if cell.formula is None:
            continue
        row, col = coordinate_to_tuple(cell.ref)
        by_col[get_column_letter(col)].append((row, cell))
    patterns: list[FormulaPattern] = []
    for col, items in sorted(by_col.items()):
        items.sort(key=lambda t: t[0])
        groups: dict[str, list[tuple[int, ir.Cell]]] = defaultdict(list)
        for row, cell in items:
            groups[_normalize(cell.formula)].append((row, cell))
        majority = max(groups, key=lambda k: len(groups[k]))
        main_rows = [r for r, _ in groups[majority]]
        main = FormulaPattern(
            ranges=[
                f"{col}{a}:{col}{b}" if a != b else f"{col}{a}" for a, b in runs(main_rows)
            ],
            pattern=majority,
            example=groups[majority][0][1].formula,
        )
        for norm, group in groups.items():
            if norm == majority:
                continue
            inside = [(r, c) for r, c in group if main_rows[0] <= r <= main_rows[-1]]
            outside = [(r, c) for r, c in group if not (main_rows[0] <= r <= main_rows[-1])]
            main.exceptions.extend(f"{c.ref}: {c.formula}" for _, c in inside)
            if outside:
                out_rows = [r for r, _ in outside]
                patterns.append(
                    FormulaPattern(
                        ranges=[
                            f"{col}{a}:{col}{b}" if a != b else f"{col}{a}"
                            for a, b in runs(out_rows)
                        ],
                        pattern=norm,
                        example=outside[0][1].formula,
                    )
                )
        patterns.append(main)
    return patterns
