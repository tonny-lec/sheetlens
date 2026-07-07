import json

from openpyxl.worksheet.datavalidation import DataValidation
from typer.testing import CliRunner

from sheetlens.cli import app

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


def test_extract_generates_project(make_xlsx):
    src = make_xlsx(_build, name="見積管理.xlsx")
    result = runner.invoke(app, ["extract", str(src)])
    assert result.exit_code == 0, result.output
    proj = src.parent / "見積管理.sheetlens"
    for rel in ("manifest.json", "questions.md", "README.md",
                "structure/raw.json", "structure/sheet-見積入力.md", "annotations"):
        assert (proj / rel).exists(), rel
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
