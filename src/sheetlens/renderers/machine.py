import re

from sheetlens.model import ir

_EXT_RE = re.compile(r"\[([^\]]+\.xls[xmb]?)\]")


def external_references(wb: ir.Workbook) -> list[str]:
    found: set[str] = set()
    for sheet in wb.sheets:
        for cell in sheet.cells:
            if cell.formula:
                found.update(_EXT_RE.findall(cell.formula))
    return sorted(found)


def sheet_dependencies(wb: ir.Workbook) -> dict[str, list[str]]:
    names = [s.name for s in wb.sheets]
    patterns = {
        name: re.compile(
            rf"(?<![\w.]){re.escape(name)}!|'{re.escape(name)}'!"
        )
        for name in names
    }
    deps: dict[str, list[str]] = {}
    for sheet in wb.sheets:
        found: set[str] = set()
        for cell in sheet.cells:
            if not cell.formula:
                continue
            for name in names:
                if name != sheet.name and patterns[name].search(cell.formula):
                    found.add(name)
        deps[sheet.name] = sorted(found)
    return deps


def build_manifest(wb: ir.Workbook) -> dict:
    return {
        "source_file": wb.source_file,
        "sha256": wb.sha256,
        "sheets": [
            {"name": s.name, "hidden": s.hidden, "used_range": s.used_range} for s in wb.sheets
        ],
        "dependencies": sheet_dependencies(wb),
        "external_refs": sorted(set(wb.external_refs) | set(external_references(wb))),
        "extraction_gaps": wb.extraction_gaps,
        "vba_modules": [m.name for m in wb.vba_modules],
    }
