from sheetlens.formulas import dependency_edges
from sheetlens.model import ir


def external_references(wb: ir.Workbook) -> list[str]:
    found: set[str] = set()
    for edge in dependency_edges(wb):
        if edge.target_workbook is None:
            continue
        if edge.target_workbook.isdigit():
            found.add(
                f"外部ブック[{edge.target_workbook}]（インデックス形式・未解決）"
            )
        else:
            found.add(edge.target_workbook)
    return sorted(found)


def _source_sheet(source: str) -> str:
    qualified = source.split(":", 1)[1].rsplit("!", 1)[0]
    if qualified.startswith("'") and qualified.endswith("'"):
        return qualified[1:-1].replace("''", "'")
    return qualified


def sheet_dependencies(wb: ir.Workbook) -> dict[str, list[str]]:
    found: dict[str, set[str]] = {sheet.name: set() for sheet in wb.sheets}
    for edge in dependency_edges(wb):
        source_sheet = _source_sheet(edge.source)
        if (
            edge.target_workbook is None
            and not edge.unresolved
            and edge.target_sheet is not None
            and edge.target_sheet != source_sheet
        ):
            found[source_sheet].add(edge.target_sheet)
    return {sheet: sorted(targets) for sheet, targets in found.items()}


def build_manifest(wb: ir.Workbook) -> dict:
    edges = dependency_edges(wb)
    return {
        "source_file": wb.source_file,
        "sha256": wb.sha256,
        "sheets": [
            {
                "name": s.name,
                "hidden": s.hidden,
                "used_range": s.used_range,
                "content_range": s.content_range,
                "structural_range": s.structural_range,
                "artifacts": [artifact.model_dump() for artifact in s.artifacts],
            }
            for s in wb.sheets
        ],
        "dependencies": sheet_dependencies(wb),
        "dependency_edges": [edge.model_dump() for edge in edges],
        "external_refs": sorted(set(wb.external_refs) | set(external_references(wb))),
        "extraction_gaps": wb.extraction_gaps,
        "vba_modules": [m.name for m in wb.vba_modules],
    }
