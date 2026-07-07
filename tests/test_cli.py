from typer.testing import CliRunner

from sheetlens.cli import app

runner = CliRunner()


def test_help_lists_three_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("extract", "compile", "check"):
        assert cmd in result.output
