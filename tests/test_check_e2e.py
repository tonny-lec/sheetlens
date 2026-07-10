import json

from openpyxl.worksheet.datavalidation import DataValidation
import pytest
from typer.testing import CliRunner

from sheetlens.cli import app
from sheetlens.model import ir
from sheetlens.pipeline import analyze
from sheetlens.question_ids import QuestionIdCatalog, build_catalog, save_catalog
from sheetlens.renderers.markdown import render_questions_md

runner = CliRunner()


def _extract(make_xlsx, name="a.xlsx", *, with_validation=False):
    def _build(wb):
        ws = wb.active
        ws.title = "入力"
        ws["A1"] = "データ"
        if with_validation:
            validation = DataValidation(type="list", formula1='"通常,特急"')
            ws.add_data_validation(validation)
            validation.add(ws["B1"])

    src = make_xlsx(_build, name=name)
    assert runner.invoke(app, ["extract", str(src)]).exit_code == 0
    return src.parent / (src.stem + ".sheetlens")


def _project_files(project):
    return {
        path.relative_to(project): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }


def _check_read_only(project):
    before = _project_files(project)
    result = runner.invoke(app, ["check", str(project)])
    assert _project_files(project) == before
    return result


def _catalog(project):
    return QuestionIdCatalog.model_validate_json(
        (project / "question-ids.json").read_text(encoding="utf-8")
    )


def _question_id(project, rule):
    catalog = _catalog(project)
    return next(
        question_id
        for question_id in catalog.current_ids
        if catalog.questions[question_id].rule == rule
    )


def _write_answer(project, question_id):
    (project / "annotations" / "入力.yaml").write_text(
        f"sheet: 入力\nquestions_answered: [{question_id}]\n",
        encoding="utf-8",
    )


def _make_legacy_project(project):
    raw = ir.Workbook.model_validate_json(
        (project / "structure" / "raw.json").read_text(encoding="utf-8")
    )
    analysis = analyze(raw)
    (project / "questions.md").write_text(
        render_questions_md(analysis.question_set.legacy_questions, set()),
        encoding="utf-8",
    )
    (project / "question-ids.json").unlink()
    return analysis


def _replace_raw_and_catalog(project, update_raw):
    catalog_path = project / "question-ids.json"
    previous = _catalog(project)
    raw_path = project / "structure" / "raw.json"
    raw = ir.Workbook.model_validate_json(raw_path.read_text(encoding="utf-8"))
    update_raw(raw)
    analysis = analyze(raw)
    raw_path.write_text(raw.model_dump_json(indent=2), encoding="utf-8")
    catalog = build_catalog(raw.sha256, analysis.question_set, previous=previous)
    save_catalog(catalog_path, catalog)
    return catalog


def test_check_resolves_current_answer_without_writes(make_xlsx):
    project = _extract(make_xlsx)
    question_id = _question_id(project, "sheet_role")
    _write_answer(project, question_id)

    result = _check_read_only(project)

    total = len(_catalog(project).current_ids)
    assert result.exit_code == 0, result.output
    assert f"未回答質問: {total - 1} / {total}" in result.output
    assert "質問ID" not in result.output


def test_check_bootstraps_legacy_aliases_in_memory_without_creating_catalog(make_xlsx):
    project = _extract(make_xlsx)
    analysis = _make_legacy_project(project)
    _write_answer(project, "q-001")

    result = _check_read_only(project)

    total = len(analysis.questions)
    assert result.exit_code == 0, result.output
    assert f"未回答質問: {total - 1} / {total}" in result.output
    assert "旧質問 ID を自動解決: 1 件" in result.output
    assert "legacy_source_sha256:" in result.output
    assert "回答時世代そのものを証明しません" in result.output
    assert not (project / "question-ids.json").exists()


def test_check_reports_changed_answer_and_current_id_without_writes(make_xlsx):
    project = _extract(make_xlsx, with_validation=True)
    old_id = _question_id(project, "list_validation")

    def change_validation(raw):
        raw.sheets[0].validations[0].formula1 = '"通常,特急,保留"'
        raw.sheets[0].validations[0].choices = ["通常", "特急", "保留"]

    catalog = _replace_raw_and_catalog(project, change_validation)
    current_id = next(
        question_id
        for question_id in catalog.current_ids
        if catalog.questions[question_id].rule == "list_validation"
    )
    _write_answer(project, old_id)

    result = _check_read_only(project)

    total = len(catalog.current_ids)
    assert result.exit_code == 0, result.output
    assert f"警告（質問ID変更）: {old_id} -> {current_id}" in result.output
    assert f"未回答質問: {total} / {total}" in result.output


def test_check_reports_deleted_answer_without_writes(make_xlsx):
    project = _extract(make_xlsx, with_validation=True)
    deleted_id = _question_id(project, "list_validation")
    catalog = _replace_raw_and_catalog(
        project,
        lambda raw: setattr(raw.sheets[0], "validations", []),
    )
    _write_answer(project, deleted_id)

    result = _check_read_only(project)

    total = len(catalog.current_ids)
    assert result.exit_code == 0, result.output
    assert f"警告（質問ID削除）: {deleted_id}" in result.output
    assert f"未回答質問: {total} / {total}" in result.output


def test_check_reports_unresolved_answer_without_writes(make_xlsx):
    project = _extract(make_xlsx)
    unknown_id = "q2-unknown-0000000000000000"
    _write_answer(project, unknown_id)

    result = _check_read_only(project)

    total = len(_catalog(project).current_ids)
    assert result.exit_code == 0, result.output
    assert f"警告（質問ID未解決）: {unknown_id}" in result.output
    assert f"未回答質問: {total} / {total}" in result.output


def test_check_rejects_catalog_source_mismatch_without_writes(make_xlsx):
    project = _extract(make_xlsx)
    catalog_path = project / "question-ids.json"
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    payload["source_sha256"] = "f" * 64
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _check_read_only(project)

    assert result.exit_code == 1
    assert "質問 ID エラー:" in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize("invalid_catalog", ["malformed", "unsupported-schema"])
def test_check_rejects_invalid_catalog_without_writes(make_xlsx, invalid_catalog):
    project = _extract(make_xlsx, name=f"{invalid_catalog}.xlsx")
    catalog_path = project / "question-ids.json"
    if invalid_catalog == "malformed":
        catalog_path.write_text("{", encoding="utf-8")
    else:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        payload["schema_version"] = 99
        catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _check_read_only(project)

    assert result.exit_code == 1
    assert "質問 ID エラー:" in result.output
    assert "Traceback" not in result.output


def test_check_rejects_ambiguous_question_identity_without_writes(make_xlsx):
    project = _extract(make_xlsx)
    raw_path = project / "structure" / "raw.json"
    raw = ir.Workbook.model_validate_json(raw_path.read_text(encoding="utf-8"))
    raw.sheets[0].validations = [
        ir.ValidationRule(
            ranges=["C5"],
            type="list",
            formula1='"通常,特急"',
            choices=["通常", "特急"],
        ),
        ir.ValidationRule(
            ranges=["C5"],
            type="list",
            formula1='"通常,特急,保留"',
            choices=["通常", "特急", "保留"],
        ),
    ]
    raw_path.write_text(raw.model_dump_json(indent=2), encoding="utf-8")

    result = _check_read_only(project)

    assert result.exit_code == 1
    assert "質問 ID エラー:" in result.output
    assert "同じ identity に異なる質問" in result.output
    assert "Traceback" not in result.output


def test_check_fails_on_schema_error_without_writes(make_xlsx):
    project = _extract(make_xlsx)
    (project / "annotations" / "bad.yaml").write_text(
        "sheet: s\ntargets:\n  - kind: nope\n", encoding="utf-8"
    )

    result = _check_read_only(project)

    assert result.exit_code == 1
    assert "bad.yaml" in result.output


def test_check_rejects_non_project(tmp_path):
    result = runner.invoke(app, ["check", str(tmp_path)])
    assert result.exit_code == 1
    assert "raw.json" in result.output


def test_extract_rejects_missing_file(tmp_path):
    result = runner.invoke(app, ["extract", str(tmp_path / "nai.xlsx")])
    assert result.exit_code != 0
    assert result.exception is None or isinstance(result.exception, SystemExit)
