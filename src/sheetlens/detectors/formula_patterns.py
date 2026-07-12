from collections import defaultdict

from openpyxl.utils import coordinate_to_tuple, get_column_letter
from pydantic import BaseModel, Field

from sheetlens.detectors.util import runs
from sheetlens.formulas import normalize_formula
from sheetlens.model import ir


class FormulaPattern(BaseModel):
    ranges: list[str]
    pattern: str
    example: str
    exceptions: list[str] = Field(default_factory=list)


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
            formula = cell.formula
            assert formula is not None
            groups[normalize_formula(formula, origin=cell.ref)].append((row, cell))
        majority = max(groups, key=lambda k: len(groups[k]))
        main_rows = [r for r, _ in groups[majority]]
        main_example = groups[majority][0][1].formula
        assert main_example is not None
        main = FormulaPattern(
            ranges=[
                f"{col}{a}:{col}{b}" if a != b else f"{col}{a}" for a, b in runs(main_rows)
            ],
            pattern=majority,
            example=main_example,
        )
        for norm, group in groups.items():
            if norm == majority:
                continue
            inside = [(r, c) for r, c in group if main_rows[0] <= r <= main_rows[-1]]
            outside = [(r, c) for r, c in group if not (main_rows[0] <= r <= main_rows[-1])]
            main.exceptions.extend(f"{c.ref}: {c.formula}" for _, c in inside)
            if outside:
                out_rows = [r for r, _ in outside]
                outside_example = outside[0][1].formula
                assert outside_example is not None
                patterns.append(
                    FormulaPattern(
                        ranges=[
                            f"{col}{a}:{col}{b}" if a != b else f"{col}{a}"
                            for a, b in runs(out_rows)
                        ],
                        pattern=norm,
                        example=outside_example,
                    )
                )
        patterns.append(main)
    return patterns
