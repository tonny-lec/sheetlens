import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from sheetlens.cli import app
from sheetlens.model import ir
from sheetlens.pipeline import analyze
from sheetlens.reader.workbook import read_workbook

FIXTURES = Path(__file__).parent / "fixtures" / "xlsm"
OPENPYXL = FIXTURES / "openpyxl-vba-test.xlsm"
OPENXML = FIXTURES / "openxml-sdk-macro.xlsm"
runner = CliRunner()


def test_real_xlsm_fixture_hashes_match_reviewed_upstream_files():
    assert hashlib.sha256(OPENPYXL.read_bytes()).hexdigest() == (
        "39ab44eb0d0725cf66baee054da963ae8292ecb41212062942fac14ce3cc59c1"
    )
    assert hashlib.sha256(OPENXML.read_bytes()).hexdigest() == (
        "6dd35cbb936ce4990c63d5747e43a363e1502a58f17c5f2ab6795849265a5d9f"
    )


def test_real_xlsm_extracts_module_event_button_questions_and_known_gaps():
    workbook = read_workbook(OPENPYXL)
    modules = {module.name: module.code for module in workbook.vba_modules}

    assert "Sub CalculateAll()" in modules["Calculations.bas"]
    assert "Private Sub Workbook_Open()" in modules["ThisWorkbook.cls"]
    assert workbook.buttons == [
        ir.ButtonLink(sheet="Scratch", macro="[0]!Button1_Click"),
    ]
    assert workbook.extraction_gaps == [
        "Scratch: drawing xl/drawings/drawing1.xml の AlternateContent は未対応です",
        "Scratch: VML drawing は未対応です",
    ]

    questions = analyze(workbook).questions
    assert any(
        question.rule == "vba_event"
        and question.target == "ThisWorkbook.cls.Workbook_Open"
        for question in questions
    )
    assert any(
        question.rule == "button_macro" and question.target == "[0]!Button1_Click"
        for question in questions
    )


def test_real_xlsm_preserves_non_ascii_vba_module_name_and_code():
    workbook = read_workbook(OPENXML)

    assert len(workbook.vba_modules) == 1
    module = workbook.vba_modules[0]
    assert module.name == "模块1.bas"
    assert "Attribute VB_Name = \"模块1\"" in module.code
    assert "Sub Macro1()" in module.code
    assert "ActiveCell.FormulaR1C1 = \"=SUM(R[-3]C:R[-1]C)\"" in module.code
    assert workbook.extraction_gaps == []


def test_extract_cli_processes_real_xlsm_without_mocking_parser(tmp_path):
    project = tmp_path / "database.sheetlens"

    result = runner.invoke(app, ["extract", str(OPENPYXL), "--out", str(project)])

    assert result.exit_code == 0, result.output
    raw = json.loads((project / "structure" / "raw.json").read_text(encoding="utf-8"))
    assert "Calculations.bas" in [module["name"] for module in raw["vba_modules"]]
    assert raw["buttons"] == [
        {"sheet": "Scratch", "label": None, "macro": "[0]!Button1_Click"},
    ]
    questions = (project / "questions.md").read_text(encoding="utf-8")
    assert "ThisWorkbook.cls.Workbook_Open" in questions
    assert "[0]!Button1_Click" in questions
