from collections import defaultdict

from openpyxl.utils import coordinate_to_tuple, get_column_letter
from pydantic import BaseModel

from sheetlens.detectors.util import runs
from sheetlens.model import ir


class Region(BaseModel):
    range: str
    kind: str  # "table" | "block"


def detect_regions(sheet: ir.Sheet) -> list[Region]:
    rows: dict[int, list[tuple[int, ir.Cell]]] = defaultdict(list)
    for cell in sheet.cells:
        r, c = coordinate_to_tuple(cell.ref)
        rows[r].append((c, cell))
    if not rows:
        return []
    regions: list[Region] = []
    for start, end in runs(sorted(rows)):
        cols = [c for r in range(start, end + 1) for c, _ in rows.get(r, [])]
        rng = f"{get_column_letter(min(cols))}{start}:{get_column_letter(max(cols))}{end}"
        head = [cell for _, cell in sorted(rows[start], key=lambda t: t[0])]
        is_table = (
            end - start + 1 >= 3
            and len(head) >= 2
            and all(isinstance(c.value, str) and c.formula is None for c in head)
        )
        regions.append(Region(range=rng, kind="table" if is_table else "block"))
    return regions
