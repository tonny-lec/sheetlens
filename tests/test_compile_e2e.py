from typer.testing import CliRunner

from sheetlens.cli import app

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
questions_answered: [q-001]
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


def test_compile_weaves_annotations(make_xlsx):
    proj = _extract(make_xlsx)
    (proj / "annotations" / "見積入力.yaml").write_text(ANNOTATION, encoding="utf-8")
    result = runner.invoke(app, ["compile", str(proj)])
    assert result.exit_code == 0, result.output
    md = (proj / "structure" / "sheet-見積入力.md").read_text(encoding="utf-8")
    assert "💬 業務上の意味: 営業担当のメイン入力画面" in md
    assert "q-001" not in md  # 回答済み質問は未確認に出ない
    assert "Z100:Z200" in result.output  # 孤立注釈の警告
    questions = (proj / "questions.md").read_text(encoding="utf-8")
    assert "- [x] **q-001**" in questions


def test_compile_rejects_broken_annotation(make_xlsx):
    proj = _extract(make_xlsx)
    (proj / "annotations" / "bad.yaml").write_text("sheet: s\ntargets:\n  - kind: nope\n", encoding="utf-8")
    result = runner.invoke(app, ["compile", str(proj)])
    assert result.exit_code == 1
    assert "bad.yaml" in result.output
