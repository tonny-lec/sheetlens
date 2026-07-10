import json

import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation
from typer.testing import CliRunner

from sheetlens.cli import app
from sheetlens.model import ir
from sheetlens.pipeline import analyze
from sheetlens.question_ids import QuestionIdCatalog, resolve_answered_ids
from sheetlens.renderers.markdown import render_questions_md

runner = CliRunner()


def _build(wb):
    ws = wb.active
    ws.title = "見積入力"
    ws["A1"] = "見積書"
    ws.merge_cells("A1:C1")
    ws["A3"] = "顧客名"
    for r in range(11, 14):
        ws[f"C{r}"] = 2
        ws[f"D{r}"] = f"=VLOOKUP(A{r},単価マスタ!A:C,3,0)"
        ws[f"E{r}"] = f"=C{r}*D{r}"
    dv = DataValidation(type="list", formula1='"通常,特急"')
    dv.add("C5")
    ws.add_data_validation(dv)
    master = wb.create_sheet("単価マスタ")
    master["A1"] = "品名"


def _make_legacy_project(proj):
    raw = ir.Workbook.model_validate_json(
        (proj / "structure" / "raw.json").read_text(encoding="utf-8")
    )
    analysis = analyze(raw)
    (proj / "questions.md").write_text(
        render_questions_md(analysis.question_set.legacy_questions, set()),
        encoding="utf-8",
    )
    (proj / "question-ids.json").unlink()


def _write_legacy_annotation(proj):
    path = proj / "annotations" / "見積入力.yaml"
    path.write_text(
        "sheet: 見積入力\nquestions_answered: [q-001]\n",
        encoding="utf-8",
    )
    return path, path.read_bytes()


def _insert_sheet_first(src, title):
    wb = openpyxl.load_workbook(src)
    wb.create_sheet(title, 0)
    wb.save(src)


def _structure_bytes(proj):
    structure = proj / "structure"
    return {
        path.relative_to(structure).as_posix(): path.read_bytes()
        for path in structure.rglob("*")
        if path.is_file()
    }


def test_extract_generates_project(make_xlsx):
    src = make_xlsx(_build, name="見積管理.xlsx")
    result = runner.invoke(app, ["extract", str(src)])
    assert result.exit_code == 0, result.output
    proj = src.parent / "見積管理.sheetlens"
    for rel in (
        "manifest.json",
        "question-ids.json",
        "questions.md",
        "README.md",
        "structure/raw.json",
        "structure/sheet-見積入力.md",
        "annotations",
    ):
        assert (proj / rel).exists(), rel
    raw = json.loads((proj / "structure/raw.json").read_text(encoding="utf-8"))
    catalog = json.loads((proj / "question-ids.json").read_text(encoding="utf-8"))
    assert catalog["schema_version"] == 1
    assert catalog["generator_version"] == 2
    assert catalog["source_sha256"] == raw["sha256"]
    manifest = json.loads((proj / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dependencies"]["見積入力"] == ["単価マスタ"]
    md = (proj / "structure/sheet-見積入力.md").read_text(encoding="utf-8")
    assert "[A1:C1 結合]" in md
    assert "=C{row}*D{row}" in md
    assert "通常" in md
    questions = (proj / "questions.md").read_text(encoding="utf-8")
    assert "dropdown_semantics" in questions and "sheet_role" in questions


def test_extract_preserves_annotations(make_xlsx):
    src = make_xlsx(_build, name="a.xlsx")
    proj = src.parent / "a.sheetlens"
    (proj / "annotations").mkdir(parents=True)
    keep = proj / "annotations" / "見積入力.yaml"
    keep.write_text("sheet: 見積入力\n", encoding="utf-8")
    result = runner.invoke(app, ["extract", str(src)])
    assert result.exit_code == 0, result.output
    assert keep.read_text(encoding="utf-8") == "sheet: 見積入力\n"


def test_reextract_bootstraps_legacy_alias_without_editing_annotations(make_xlsx):
    src = make_xlsx(_build, name="legacy.xlsx")
    assert runner.invoke(app, ["extract", str(src)]).exit_code == 0
    proj = src.parent / "legacy.sheetlens"
    old_raw = ir.Workbook.model_validate_json(
        (proj / "structure/raw.json").read_text(encoding="utf-8")
    )
    _make_legacy_project(proj)
    annotation, annotation_bytes = _write_legacy_annotation(proj)

    _insert_sheet_first(src, "新規入力")
    result = runner.invoke(app, ["extract", str(src)])

    assert result.exit_code == 0, result.output
    catalog = QuestionIdCatalog.model_validate_json(
        (proj / "question-ids.json").read_text(encoding="utf-8")
    )
    target = catalog.legacy_aliases["q-001"]
    assert catalog.questions[target].rule == "sheet_role"
    assert catalog.questions[target].sheet == "見積入力"
    assert catalog.legacy_source_sha256 == old_raw.sha256
    new_raw = ir.Workbook.model_validate_json(
        (proj / "structure/raw.json").read_text(encoding="utf-8")
    )
    assert catalog.source_sha256 == new_raw.sha256
    assert annotation.read_bytes() == annotation_bytes


def test_changed_legacy_questions_prevents_alias_and_preserves_annotations(make_xlsx):
    src = make_xlsx(_build, name="changed-questions.xlsx")
    assert runner.invoke(app, ["extract", str(src)]).exit_code == 0
    proj = src.parent / "changed-questions.sheetlens"
    _make_legacy_project(proj)
    questions_path = proj / "questions.md"
    questions_path.write_text(
        questions_path.read_text(encoding="utf-8").replace("シート", "改変シート", 1),
        encoding="utf-8",
    )
    annotation, annotation_bytes = _write_legacy_annotation(proj)

    result = runner.invoke(app, ["extract", str(src)])

    assert result.exit_code == 0, result.output
    catalog = QuestionIdCatalog.model_validate_json(
        (proj / "question-ids.json").read_text(encoding="utf-8")
    )
    resolution = resolve_answered_ids(["q-001"], catalog)
    assert catalog.legacy_aliases == {}
    assert catalog.legacy_source_sha256 is None
    assert [diagnostic.model_dump() for diagnostic in resolution.diagnostics] == [
        {"kind": "unresolved", "question_id": "q-001", "current_id": None}
    ]
    assert annotation.read_bytes() == annotation_bytes


def test_second_reextract_does_not_repoint_legacy_alias(make_xlsx):
    src = make_xlsx(_build, name="alias-history.xlsx")
    assert runner.invoke(app, ["extract", str(src)]).exit_code == 0
    proj = src.parent / "alias-history.sheetlens"
    _make_legacy_project(proj)
    annotation, annotation_bytes = _write_legacy_annotation(proj)
    _insert_sheet_first(src, "追加1")
    assert runner.invoke(app, ["extract", str(src)]).exit_code == 0
    first_catalog = QuestionIdCatalog.model_validate_json(
        (proj / "question-ids.json").read_text(encoding="utf-8")
    )
    original_target = first_catalog.legacy_aliases["q-001"]

    _insert_sheet_first(src, "追加2")
    result = runner.invoke(app, ["extract", str(src)])

    assert result.exit_code == 0, result.output
    second_catalog = QuestionIdCatalog.model_validate_json(
        (proj / "question-ids.json").read_text(encoding="utf-8")
    )
    assert second_catalog.legacy_aliases["q-001"] == original_target
    assert second_catalog.questions[original_target].sheet == "見積入力"
    assert annotation.read_bytes() == annotation_bytes


def test_reextract_rejects_catalog_source_tampering_before_deleting_structure(make_xlsx):
    src = make_xlsx(_build, name="tampered-catalog.xlsx")
    assert runner.invoke(app, ["extract", str(src)]).exit_code == 0
    proj = src.parent / "tampered-catalog.sheetlens"
    annotation, annotation_bytes = _write_legacy_annotation(proj)
    raw_bytes = (proj / "structure/raw.json").read_bytes()
    catalog_path = proj / "question-ids.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["source_sha256"] = "f" * 64
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    result = runner.invoke(app, ["extract", str(src)])

    assert result.exit_code == 1
    assert "質問 ID エラー:" in result.output
    assert "Traceback" not in result.output
    assert (proj / "structure/raw.json").read_bytes() == raw_bytes
    assert annotation.read_bytes() == annotation_bytes


def test_reextract_identity_error_preserves_entire_structure_and_annotations(make_xlsx):
    src = make_xlsx(_build, name="ambiguous.xlsx")
    assert runner.invoke(app, ["extract", str(src)]).exit_code == 0
    proj = src.parent / "ambiguous.sheetlens"
    annotation, annotation_bytes = _write_legacy_annotation(proj)
    structure_bytes = _structure_bytes(proj)
    wb = openpyxl.load_workbook(src)
    duplicate = DataValidation(type="list", formula1='"通常,特急,保留"')
    duplicate.add("C5")
    wb["見積入力"].add_data_validation(duplicate)
    wb.save(src)

    result = runner.invoke(app, ["extract", str(src)])

    assert result.exit_code == 1
    assert "質問 ID エラー:" in result.output
    assert "Traceback" not in result.output
    assert _structure_bytes(proj) == structure_bytes
    assert annotation.read_bytes() == annotation_bytes


def test_reextract_removes_stale_structure_files(make_xlsx):
    src = make_xlsx(_build, name="b.xlsx")
    assert runner.invoke(app, ["extract", str(src)]).exit_code == 0
    proj = src.parent / "b.sheetlens"
    stale = proj / "structure" / "sheet-消えたシート.md"
    stale.write_text("stale", encoding="utf-8")
    keep = proj / "annotations" / "残す.yaml"
    keep.write_text("sheet: 見積入力\n", encoding="utf-8")
    assert runner.invoke(app, ["extract", str(src)]).exit_code == 0
    assert not stale.exists()
    assert keep.exists()


def test_extract_refuses_foreign_structure_dir(make_xlsx, tmp_path):
    src = make_xlsx(_build, name="c.xlsx")
    out = tmp_path / "userproj"
    (out / "structure").mkdir(parents=True)
    user_file = out / "structure" / "main.c"
    user_file.write_text("int main(){}", encoding="utf-8")
    result = runner.invoke(app, ["extract", str(src), "-o", str(out)])
    assert result.exit_code == 1
    assert user_file.exists()
    assert "raw.json" in result.output


def test_extract_rejects_broken_file(tmp_path):
    bad = tmp_path / "broken.xlsx"
    bad.write_bytes(b"not a zip")
    result = runner.invoke(app, ["extract", str(bad)])
    assert result.exit_code == 1
    assert "読めません" in result.output
