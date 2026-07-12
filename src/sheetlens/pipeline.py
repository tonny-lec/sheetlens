import json
import os
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from sheetlens.annotations.schema import SheetAnnotations, find_orphans, load_annotations, split_ranges
from sheetlens.detectors.formula_patterns import FormulaPattern, aggregate_formulas
from sheetlens.detectors.questions import Question, QuestionSet, generate_question_set
from sheetlens.detectors.regions import Region, detect_regions
from sheetlens.model import ir
from sheetlens.question_ids import (
    AnswerResolution,
    QuestionIdCatalog,
    build_catalog,
    is_legacy_question_id,
    legacy_snapshot_matches,
    load_catalog,
    record_unresolved_legacy_ids,
    resolve_answered_ids,
    save_catalog,
    validate_catalog_questions,
)
from sheetlens.reader.workbook import read_workbook
from sheetlens.renderers.machine import build_manifest, sheet_dependencies
from sheetlens.renderers.markdown import render_questions_md, render_readme, render_sheet_md


class Analysis(BaseModel):
    patterns: dict[str, list[FormulaPattern]]
    regions: dict[str, list[Region]]
    question_set: QuestionSet

    @property
    def questions(self) -> list[Question]:
        return self.question_set.questions


class ProjectQuestionState(BaseModel):
    catalog: QuestionIdCatalog
    resolution: AnswerResolution
    bootstrapped_catalog: bool = False
    answer_diagnostics: list["AnnotationAnswerDiagnostic"] = Field(default_factory=list)


class AnnotationAnswerDiagnostic(BaseModel):
    kind: Literal["target_mismatch", "empty_answer"]
    question_id: str
    annotation_sheet: str
    question_sheet: str


class CompileResult(BaseModel):
    warnings: list[str]
    question_state: ProjectQuestionState


class ExistingStructureError(Exception):
    pass


class ProjectRecoveryError(Exception):
    pass


class PostCommitCleanupError(Exception):
    def __init__(self, project: Path, backup: Path, cause: OSError):
        self.project = project
        self.backup = backup
        super().__init__(
            f"{project} の生成は完了しましたが、backup {backup} を削除できません: {cause}"
        )


def analyze(wb: ir.Workbook) -> Analysis:
    patterns = {s.name: aggregate_formulas(s) for s in wb.sheets}
    regions = {s.name: detect_regions(s) for s in wb.sheets}
    return Analysis(
        patterns=patterns,
        regions=regions,
        question_set=generate_question_set(wb, regions, patterns),
    )


def bootstrap_legacy_catalog(
    proj: Path,
    wb: ir.Workbook,
    analysis: Analysis,
) -> QuestionIdCatalog:
    expected = render_questions_md(analysis.question_set.legacy_questions, set())
    questions_path = proj / "questions.md"
    legacy_aliases: dict[str, str] = {}
    if questions_path.exists():
        existing = questions_path.read_text(encoding="utf-8")
        if legacy_snapshot_matches(existing, expected):
            legacy_aliases = analysis.question_set.legacy_aliases
    return build_catalog(
        wb.sha256,
        analysis.question_set,
        legacy_aliases=legacy_aliases,
        legacy_source_sha256=wb.sha256 if legacy_aliases else None,
    )


def _load_or_bootstrap_question_catalog(
    proj: Path,
    wb: ir.Workbook,
    analysis: Analysis,
) -> tuple[QuestionIdCatalog, bool]:
    catalog = load_catalog(
        proj / "question-ids.json",
        expected_source_sha256=wb.sha256,
    )
    bootstrapped_catalog = catalog is None
    if catalog is None:
        catalog = bootstrap_legacy_catalog(proj, wb, analysis)
    validate_catalog_questions(catalog, analysis.question_set)
    return catalog, bootstrapped_catalog


def resolve_project_question_ids(
    proj: Path,
    wb: ir.Workbook,
    analysis: Analysis,
    anns: list[SheetAnnotations],
    *,
    persist: bool,
) -> ProjectQuestionState:
    catalog_path = proj / "question-ids.json"
    catalog, bootstrapped_catalog = _load_or_bootstrap_question_catalog(
        proj,
        wb,
        analysis,
    )
    annotation_ids = [qid for ann in anns for qid in ann.questions_answered]
    resolution = resolve_answered_ids(annotation_ids, catalog)
    catalog = record_unresolved_legacy_ids(
        catalog,
        (
            diagnostic.question_id
            for diagnostic in resolution.diagnostics
            if diagnostic.kind == "unresolved"
            and is_legacy_question_id(diagnostic.question_id)
        ),
    )
    if persist:
        save_catalog(catalog_path, catalog)
    answer_diagnostics = _validate_annotation_answers(catalog, anns, resolution)
    return ProjectQuestionState(
        catalog=catalog,
        resolution=resolution,
        bootstrapped_catalog=bootstrapped_catalog,
        answer_diagnostics=answer_diagnostics,
    )


def _resolved_question_id(question_id: str, catalog: QuestionIdCatalog) -> str:
    if is_legacy_question_id(question_id):
        return catalog.legacy_aliases.get(question_id, question_id)
    return question_id


def _normalized_target(value: str) -> tuple[str, ...]:
    return tuple(sorted(part.upper() for part in split_ranges(value)))


def _has_annotation_answer(
    ann: SheetAnnotations,
    question: object,
) -> bool:
    category = question.category
    if category == "sheet_role":
        return bool(ann.role and ann.role.strip()) or any(
            target.kind == "sheet_role"
            and bool(getattr(target, "note", None) or getattr(target, "value", None))
            for target in ann.targets
        )
    if category == "free_note":
        return False
    for target in ann.targets:
        target_range = getattr(target, "range", None)
        if target.kind != category or not target_range:
            continue
        if category == "trigger_timing":
            matches = target_range == question.target
        else:
            matches = _normalized_target(target_range) == _normalized_target(question.target)
        if not matches:
            continue
        if category == "input_source":
            return bool(getattr(target, "value", None))
        if category == "dropdown_semantics":
            values = getattr(target, "values", {})
            return bool(values) and all(key.strip() and value.strip() for key, value in values.items())
        if category == "trigger_timing":
            return bool(getattr(target, "when", None))
        return bool(getattr(target, "note", None) or getattr(target, "value", None))
    return False


def _validate_annotation_answers(
    catalog: QuestionIdCatalog,
    anns: list[SheetAnnotations],
    resolution: AnswerResolution,
) -> list[AnnotationAnswerDiagnostic]:
    diagnostics: list[AnnotationAnswerDiagnostic] = []
    answered_ids = set(resolution.answered_ids)
    for ann in anns:
        for source_id in ann.questions_answered:
            target_id = _resolved_question_id(source_id, catalog)
            question = catalog.questions.get(target_id)
            if question is None or target_id not in answered_ids:
                continue
            if ann.sheet != question.sheet:
                answered_ids.discard(target_id)
                diagnostics.append(
                    AnnotationAnswerDiagnostic(
                        kind="target_mismatch",
                        question_id=source_id,
                        annotation_sheet=ann.sheet,
                        question_sheet=question.sheet,
                    )
                )
                continue
            if not _has_annotation_answer(ann, question):
                answered_ids.discard(target_id)
                diagnostics.append(
                    AnnotationAnswerDiagnostic(
                        kind="empty_answer",
                        question_id=source_id,
                        annotation_sheet=ann.sheet,
                        question_sheet=question.sheet,
                    )
                )
    resolution.answered_ids = answered_ids
    return diagnostics


def _safe(name: str) -> str:
    return name.replace("/", "_")


def find_unwoven(wb: ir.Workbook, analysis: Analysis, anns: list[SheetAnnotations]) -> list[str]:
    trigger_targets = {
        (question.sheet, question.target)
        for question in analysis.questions
        if question.category == "trigger_timing"
    }
    warnings: list[str] = []
    for ann in anns:
        sheet = next((s for s in wb.sheets if s.name == ann.sheet), None)
        if sheet is None:
            if ann.sheet == "(VBA)":
                for target in ann.targets:
                    target_range = getattr(target, "range", None)
                    if (
                        target.kind == "trigger_timing"
                        and target_range
                        and (ann.sheet, target_range) not in trigger_targets
                    ):
                        warnings.append(
                            f"{ann.sheet}!{target_range}: 該当するマクロがありません（織り込まれません）"
                        )
            continue
        keys: set[str] = {r.range for r in analysis.regions.get(ann.sheet, [])}
        for v in sheet.validations:
            keys.update(v.ranges)
        for cf in sheet.conditional_formats:
            keys.update(split_ranges(cf.range))
        for t in ann.targets:
            target_range = getattr(t, "range", None)
            if not target_range or t.kind == "hidden_reason":
                continue
            if t.kind == "trigger_timing":
                if (ann.sheet, target_range) not in trigger_targets:
                    warnings.append(
                        f"{ann.sheet}!{target_range}: 該当するマクロがありません（織り込まれません）"
                    )
                continue
            if not any(part in keys for part in split_ranges(target_range)):
                warnings.append(
                    f"{ann.sheet}!{target_range}: どの構造要素にも一致しませんでした（織り込まれません）"
                )
    return warnings


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
        render_readme(
            wb,
            sheet_dependencies(wb),
            analysis.questions,
            answered,
            anns,
        ),
        encoding="utf-8",
    )
    (proj / "questions.md").write_text(
        render_questions_md(analysis.questions, answered), encoding="utf-8"
    )


_MANAGED_PROJECT_PATHS = (
    "structure",
    "manifest.json",
    "question-ids.json",
    "questions.md",
    "README.md",
    "annotations",
)


def _transaction_paths(proj: Path) -> tuple[Path, Path, Path]:
    prefix = f".{proj.name}.sheetlens-transaction"
    return (
        proj.parent / f"{prefix}.stage",
        proj.parent / f"{prefix}.backup",
        proj.parent / f"{prefix}.lock",
    )


def _reject_unsafe_project_paths(proj: Path) -> None:
    if proj.is_symlink():
        raise ExistingStructureError(
            f"{proj} はsymlinkのため安全に置換できません。実体pathを出力先に指定してください。"
        )
    if proj.exists() and not proj.is_dir():
        raise ExistingStructureError(
            f"{proj} はdirectoryではありません。別の出力先を指定してください。"
        )
    for relative in _MANAGED_PROJECT_PATHS:
        path = proj / relative
        if path.is_symlink():
            raise ExistingStructureError(
                f"{path} はsymlinkのため安全に置換できません。symlinkを解消して再実行してください。"
            )


def _write_extracted_project(
    proj: Path,
    wb: ir.Workbook,
    analysis: Analysis,
    catalog: QuestionIdCatalog,
) -> None:
    structure_dir = proj / "structure"
    structure_dir.mkdir(parents=True)
    (proj / "annotations").mkdir(exist_ok=True)
    (structure_dir / "raw.json").write_text(
        wb.model_dump_json(indent=2), encoding="utf-8"
    )
    (proj / "manifest.json").write_text(
        json.dumps(build_manifest(wb), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if wb.vba_modules:
        vba_dir = structure_dir / "vba"
        vba_dir.mkdir(exist_ok=True)
        for module in wb.vba_modules:
            name = _safe(module.name)
            if "." not in name:
                name += ".bas"
            (vba_dir / name).write_text(module.code, encoding="utf-8")
    _write_views(proj, wb, analysis, [], set())
    save_catalog(proj / "question-ids.json", catalog)


def _validate_staged_project(
    proj: Path,
    expected: ir.Workbook,
    analysis: Analysis,
) -> None:
    raw_path = proj / "structure" / "raw.json"
    staged = ir.Workbook.model_validate_json(raw_path.read_text(encoding="utf-8"))
    if staged.sha256 != expected.sha256:
        raise ExistingStructureError(
            f"{raw_path} のsource hashが生成対象と一致しません。再実行してください。"
        )
    json.loads((proj / "manifest.json").read_text(encoding="utf-8"))
    catalog = load_catalog(
        proj / "question-ids.json",
        expected_source_sha256=expected.sha256,
    )
    if catalog is None:
        raise ExistingStructureError(
            f"{proj / 'question-ids.json'} を検証できません。再実行してください。"
        )
    validate_catalog_questions(catalog, analysis.question_set)
    required = [proj / "README.md", proj / "questions.md"]
    required.extend(
        proj / "structure" / f"sheet-{_safe(sheet.name)}.md"
        for sheet in expected.sheets
    )
    required.extend(
        proj
        / "structure"
        / "vba"
        / (
            _safe(module.name)
            if "." in _safe(module.name)
            else f"{_safe(module.name)}.bas"
        )
        for module in expected.vba_modules
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ExistingStructureError(
            f"staging成果物が不足しています: {', '.join(missing)}。再実行してください。"
        )


def _swap_staged_project(proj: Path, stage: Path, backup: Path) -> None:
    if not proj.exists():
        stage.replace(proj)
        return
    proj.replace(backup)
    try:
        stage.replace(proj)
    except OSError as swap_error:
        try:
            backup.replace(proj)
        except OSError as rollback_error:
            raise ProjectRecoveryError(
                f"project置換とrollbackの両方に失敗しました。手動で復旧してください: "
                f"project={proj}, backup={backup}, stage={stage}, "
                f"swap_error={swap_error}, rollback_error={rollback_error}"
            ) from rollback_error
        raise
    try:
        shutil.rmtree(backup)
    except OSError as exc:
        raise PostCommitCleanupError(proj, backup, exc) from exc


def extract_workbook(src: Path, out: Path | None = None) -> Path:
    wb = read_workbook(src)
    proj = out or src.with_name(src.stem + ".sheetlens")
    analysis = analyze(wb)
    structure_dir = proj / "structure"
    raw_path = structure_dir / "raw.json"

    proj.parent.mkdir(parents=True, exist_ok=True)
    _reject_unsafe_project_paths(proj)

    if (proj / "question-ids.json").exists() and not raw_path.exists():
        raise ExistingStructureError(
            f"{proj} は question-ids.json が存在しますが structure/raw.json がありません。"
            "catalog の履歴を保護するため中断しました。"
        )

    if structure_dir.exists():
        if not raw_path.exists():
            raise ExistingStructureError(
                f"{structure_dir} は SheetLens の出力ではありません（raw.json なし）。"
                "誤削除を防ぐため中断しました。別の出力先を指定してください。"
            )
        old_wb = ir.Workbook.model_validate_json(raw_path.read_text(encoding="utf-8"))
        old_analysis = analyze(old_wb)
        old_catalog, _ = _load_or_bootstrap_question_catalog(
            proj,
            old_wb,
            old_analysis,
        )
        catalog = build_catalog(
            wb.sha256,
            analysis.question_set,
            previous=old_catalog,
        )
        validate_catalog_questions(catalog, analysis.question_set)
    else:
        catalog = build_catalog(wb.sha256, analysis.question_set)

    stage, backup, lock = _transaction_paths(proj)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ExistingStructureError(
            f"{lock} が存在するため別のextractが実行中か、前回処理が中断しています。"
            "状態を確認して手動で復旧してください。"
        ) from exc
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
    except OSError:
        lock.unlink(missing_ok=True)
        raise
    finally:
        os.close(descriptor)
    preserve_stage = False
    preserve_lock = False
    try:
        stale = [path for path in (stage, backup) if path.exists() or path.is_symlink()]
        if stale:
            preserve_stage = stage in stale
            raise ExistingStructureError(
                "前回transactionの残存pathがあります。自動削除せず中断しました: "
                f"{', '.join(str(path) for path in stale)}。内容を確認して手動復旧してください。"
            )
        if proj.exists():
            shutil.copytree(proj, stage, symlinks=True)
            staged_structure = stage / "structure"
            if staged_structure.exists():
                shutil.rmtree(staged_structure)
        else:
            stage.mkdir()
        _write_extracted_project(stage, wb, analysis, catalog)
        _validate_staged_project(stage, wb, analysis)
        try:
            _swap_staged_project(proj, stage, backup)
        except ProjectRecoveryError:
            preserve_stage = True
            preserve_lock = True
            raise
    finally:
        try:
            if not preserve_stage and stage.exists():
                shutil.rmtree(stage)
        finally:
            if not preserve_lock:
                lock.unlink(missing_ok=True)
    return proj


def compile_project(proj: Path) -> CompileResult:
    wb = ir.Workbook.model_validate_json(
        (proj / "structure" / "raw.json").read_text(encoding="utf-8")
    )
    anns = load_annotations(proj / "annotations")
    analysis = analyze(wb)
    question_state = resolve_project_question_ids(
        proj,
        wb,
        analysis,
        anns,
        persist=True,
    )
    _write_views(
        proj,
        wb,
        analysis,
        anns,
        question_state.resolution.answered_ids,
    )
    return CompileResult(
        warnings=find_orphans(wb, anns) + find_unwoven(wb, analysis, anns),
        question_state=question_state,
    )
