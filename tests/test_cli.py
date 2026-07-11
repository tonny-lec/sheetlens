import errno

from typer.testing import CliRunner

from sheetlens.cli import app
import sheetlens.pipeline as pipeline

runner = CliRunner()


def test_help_lists_three_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("extract", "compile", "check"):
        assert cmd in result.output


def test_extract_formats_oserror_with_path_and_recovery(tmp_path, monkeypatch):
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"placeholder")
    output = tmp_path / "output.sheetlens"

    def fail(_source, _output):
        raise OSError(errno.ENOSPC, "disk full", str(output))

    monkeypatch.setattr(pipeline, "extract_workbook", fail)
    result = runner.invoke(app, ["extract", str(source), "--out", str(output)])

    assert result.exit_code == 1
    assert "I/Oエラー" in result.output
    assert str(output) in result.output
    assert "権限・空き容量" in result.output
    assert "extractを再実行" in result.output
    assert "Traceback" not in result.output
