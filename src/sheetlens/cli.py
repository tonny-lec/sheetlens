from pathlib import Path
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException
import typer

app = typer.Typer(help="業務 Excel を AI が誤読しない中間表現に変換する", no_args_is_help=True)


@app.command()
def extract(file: Path, out: Path | None = typer.Option(None, "-o", "--out")) -> None:
    """xlsx/xlsm から構造層と questions.md を生成する。"""
    from sheetlens.pipeline import extract_workbook

    try:
        proj = extract_workbook(file, out)
    except (InvalidFileException, BadZipFile, KeyError) as e:
        typer.echo(f"エラー: {file} を読めません（破損またはパスワード保護の可能性）: {e}")
        raise typer.Exit(1) from e
    typer.echo(f"生成しました: {proj}")


@app.command(name="compile")
def compile_cmd(project: Path) -> None:
    """構造層 + 注釈を統合した Markdown を再生成する。"""
    from sheetlens.annotations.schema import AnnotationError
    from sheetlens.pipeline import compile_project

    try:
        orphans = compile_project(project)
    except AnnotationError as e:
        typer.echo(f"注釈エラー: {e}")
        raise typer.Exit(1) from e
    for o in orphans:
        typer.echo(f"警告（孤立注釈）: {o}")
    typer.echo(f"再生成しました: {project}")


@app.command()
def check(project: Path) -> None:
    """孤立注釈・未回答質問・スキーマ違反を報告する。"""
    typer.echo("check: 未実装")
    raise typer.Exit(1)
