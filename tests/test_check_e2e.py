from typer.testing import CliRunner

from sheetlens.cli import app

runner = CliRunner()


def _extract(make_xlsx, name="a.xlsx"):
    def _build(wb):
        ws = wb.active
        ws.title = "入力"
        ws["A1"] = "データ"

    src = make_xlsx(_build, name=name)
    assert runner.invoke(app, ["extract", str(src)]).exit_code == 0
    return src.parent / (src.stem + ".sheetlens")


def test_check_reports_counts(make_xlsx):
    proj = _extract(make_xlsx)
    (proj / "annotations" / "入力.yaml").write_text(
        "sheet: 入力\nquestions_answered: [q-001]\n", encoding="utf-8"
    )
    result = runner.invoke(app, ["check", str(proj)])
    assert result.exit_code == 0, result.output
    assert "未回答質問:" in result.output


def test_check_fails_on_schema_error(make_xlsx):
    proj = _extract(make_xlsx)
    (proj / "annotations" / "bad.yaml").write_text("sheet: s\ntargets:\n  - kind: nope\n", encoding="utf-8")
    result = runner.invoke(app, ["check", str(proj)])
    assert result.exit_code == 1
    assert "bad.yaml" in result.output
