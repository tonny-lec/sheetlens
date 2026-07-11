import json

import pytest
from typer.testing import CliRunner

from sheetlens.cli import app
from sheetlens.model import ir
from sheetlens.pipeline import analyze
from sheetlens.question_ids import QuestionIdCatalog
from sheetlens.renderers.markdown import render_questions_md

runner = CliRunner()

ANNOTATION = """\
sheet: 見積入力
role: "営業担当のメイン入力画面"
targets:
  - range: A3:B3
    kind: input_source
    value: manual
    by: "営業担当"
  - range: Z100:Z200
    kind: free_note
    note: "消えた範囲への注釈"
questions_answered: [{question_id}]
"""


def _extract(make_xlsx):
    def _build(wb):
        ws = wb.active
        ws.title = "見積入力"
        ws["A3"] = "顧客名"
        ws["B3"] = "株式会社サンプル"

    src = make_xlsx(_build, name="a.xlsx")
    assert runner.invoke(app, ["extract", str(src)]).exit_code == 0
    return src.parent / "a.sheetlens"


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


def _write_annotation(proj, question_id):
    path = proj / "annotations" / "見積入力.yaml"
    path.write_text(ANNOTATION.format(question_id=question_id), encoding="utf-8")
    return path


def _sheet_role_id(proj):
    catalog = QuestionIdCatalog.model_validate_json(
        (proj / "question-ids.json").read_text(encoding="utf-8")
    )
    return next(
        question_id
        for question_id in catalog.current_ids
        if catalog.questions[question_id].rule == "sheet_role"
        and catalog.questions[question_id].sheet == "見積入力"
    )


def test_compile_weaves_annotations(make_xlsx):
    proj = _extract(make_xlsx)
    question_id = _sheet_role_id(proj)
    _write_annotation(proj, question_id)
    result = runner.invoke(app, ["compile", str(proj)])
    assert result.exit_code == 0, result.output
    md = (proj / "structure" / "sheet-見積入力.md").read_text(encoding="utf-8")
    assert "💬 業務上の意味: 営業担当のメイン入力画面" in md
    assert question_id not in md  # 回答済み質問は未確認に出ない
    assert "Z100:Z200" in result.output  # 孤立注釈の警告
    questions = (proj / "questions.md").read_text(encoding="utf-8")
    assert f"- [x] **{question_id}**" in questions


def test_compile_resolves_legacy_answer_without_rewriting_annotation(make_xlsx):
    proj = _extract(make_xlsx)
    _make_legacy_project(proj)
    annotation_path = _write_annotation(proj, "q-001")
    before = annotation_path.read_bytes()

    result = runner.invoke(app, ["compile", str(proj)])

    assert result.exit_code == 0, result.output
    assert annotation_path.read_bytes() == before
    assert "旧質問 ID を自動解決: 1 件" in result.output
    assert "回答時世代そのものを証明しません" in result.output
    questions = (proj / "questions.md").read_text(encoding="utf-8")
    assert "**q2-sheet_role-" in questions
    assert "- [x] **q2-sheet_role-" in questions
    catalog = QuestionIdCatalog.model_validate_json(
        (proj / "question-ids.json").read_text(encoding="utf-8")
    )
    assert catalog.legacy_source_sha256 in result.output


def test_compile_leaves_legacy_answer_unresolved_when_snapshot_changed(make_xlsx):
    proj = _extract(make_xlsx)
    _make_legacy_project(proj)
    questions_path = proj / "questions.md"
    questions_path.write_text(
        questions_path.read_text(encoding="utf-8").replace("シート", "改変シート", 1),
        encoding="utf-8",
    )
    annotation_path = _write_annotation(proj, "q-001")
    before = annotation_path.read_bytes()

    result = runner.invoke(app, ["compile", str(proj)])

    assert result.exit_code == 0, result.output
    assert annotation_path.read_bytes() == before
    assert "警告（質問ID未解決）: q-001" in result.output
    assert "旧質問 ID を自動解決" not in result.output
    questions = questions_path.read_text(encoding="utf-8")
    assert "- [ ] **q2-sheet_role-" in questions
    catalog = QuestionIdCatalog.model_validate_json(
        (proj / "question-ids.json").read_text(encoding="utf-8")
    )
    assert catalog.legacy_aliases == {}
    assert catalog.unresolved_legacy_ids == ["q-001"]


def test_compile_rejects_catalog_source_mismatch(make_xlsx):
    proj = _extract(make_xlsx)
    questions_before = (proj / "questions.md").read_bytes()
    catalog_path = proj / "question-ids.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["source_sha256"] = "f" * 64
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    result = runner.invoke(app, ["compile", str(proj)])

    assert result.exit_code == 1
    assert "質問 ID エラー:" in result.output
    assert "Traceback" not in result.output
    assert (proj / "questions.md").read_bytes() == questions_before


def test_compile_rejects_ambiguous_question_identity(make_xlsx):
    proj = _extract(make_xlsx)
    questions_before = (proj / "questions.md").read_bytes()
    raw_path = proj / "structure" / "raw.json"
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

    result = runner.invoke(app, ["compile", str(proj)])

    assert result.exit_code == 1
    assert "質問 ID エラー:" in result.output
    assert "同じ identity に異なる質問" in result.output
    assert "Traceback" not in result.output
    assert (proj / "questions.md").read_bytes() == questions_before


def test_compile_rejects_broken_annotation(make_xlsx):
    proj = _extract(make_xlsx)
    (proj / "annotations" / "bad.yaml").write_text("sheet: s\ntargets:\n  - kind: nope\n", encoding="utf-8")
    result = runner.invoke(app, ["compile", str(proj)])
    assert result.exit_code == 1
    assert "bad.yaml" in result.output


@pytest.mark.parametrize("raw_text", ["{", "{}"])
def test_compile_formats_broken_raw_as_recoverable_data_error(make_xlsx, raw_text):
    proj = _extract(make_xlsx)
    raw_path = proj / "structure" / "raw.json"
    raw_path.write_text(raw_text, encoding="utf-8")

    result = runner.invoke(app, ["compile", str(proj)])

    assert result.exit_code == 1
    assert "データエラー" in result.output
    assert str(raw_path) in result.output
    assert "extractを再実行" in result.output
    assert "Traceback" not in result.output
