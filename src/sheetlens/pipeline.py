import json
from pathlib import Path

from pydantic import BaseModel

from sheetlens.annotations.schema import SheetAnnotations, find_orphans, load_annotations
from sheetlens.detectors.formula_patterns import FormulaPattern, aggregate_formulas
from sheetlens.detectors.questions import Question, generate_questions
from sheetlens.detectors.regions import Region, detect_regions
from sheetlens.model import ir
from sheetlens.reader.workbook import read_workbook
from sheetlens.renderers.machine import build_manifest, sheet_dependencies
from sheetlens.renderers.markdown import render_questions_md, render_readme, render_sheet_md


class Analysis(BaseModel):
    patterns: dict[str, list[FormulaPattern]]
    regions: dict[str, list[Region]]
    questions: list[Question]


def analyze(wb: ir.Workbook) -> Analysis:
    patterns = {s.name: aggregate_formulas(s) for s in wb.sheets}
    regions = {s.name: detect_regions(s) for s in wb.sheets}
    return Analysis(
        patterns=patterns, regions=regions, questions=generate_questions(wb, regions, patterns)
    )


def _safe(name: str) -> str:
    return name.replace("/", "_")


def _write_views(
    proj: Path,
    wb: ir.Workbook,
    analysis: Analysis,
    anns: list[SheetAnnotations],
    answered: set[str],
) -> None:
    structure = proj / "structure"
    ann_map = {a.sheet: a for a in anns}
    for sheet in wb.sheets:
        md = render_sheet_md(
            sheet,
            analysis.patterns[sheet.name],
            analysis.regions[sheet.name],
            analysis.questions,
            [b for b in wb.buttons if b.sheet == sheet.name],
            ann_map.get(sheet.name),
            answered,
        )
        (structure / f"sheet-{_safe(sheet.name)}.md").write_text(md, encoding="utf-8")
    (proj / "README.md").write_text(
        render_readme(wb, sheet_dependencies(wb), analysis.questions, answered), encoding="utf-8"
    )
    (proj / "questions.md").write_text(
        render_questions_md(analysis.questions, answered), encoding="utf-8"
    )


def extract_workbook(src: Path, out: Path | None = None) -> Path:
    wb = read_workbook(src)
    proj = out or src.with_name(src.stem + ".sheetlens")
    (proj / "structure").mkdir(parents=True, exist_ok=True)
    (proj / "annotations").mkdir(exist_ok=True)  # 既存の中身には触れない
    (proj / "structure" / "raw.json").write_text(wb.model_dump_json(indent=2), encoding="utf-8")
    (proj / "manifest.json").write_text(
        json.dumps(build_manifest(wb), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if wb.vba_modules:
        vba_dir = proj / "structure" / "vba"
        vba_dir.mkdir(exist_ok=True)
        for m in wb.vba_modules:
            (vba_dir / f"{_safe(m.name)}.bas").write_text(m.code, encoding="utf-8")
    # extract は注釈なしのビューを書く（織り込みは compile の仕事）
    _write_views(proj, wb, analyze(wb), [], set())
    return proj


def compile_project(proj: Path) -> list[str]:
    wb = ir.Workbook.model_validate_json(
        (proj / "structure" / "raw.json").read_text(encoding="utf-8")
    )
    anns = load_annotations(proj / "annotations")
    answered = {qid for a in anns for qid in a.questions_answered}
    _write_views(proj, wb, analyze(wb), anns, answered)
    return find_orphans(wb, anns)
