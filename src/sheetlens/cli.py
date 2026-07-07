from pathlib import Path
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException
import typer

app = typer.Typer(help="業務 Excel を AI が誤読しない中間表現に変換する", no_args_is_help=True)


@app.command()
def extract(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    out: Path | None = typer.Option(None, "-o", "--out"),
) -> None:
    """xlsx/xlsm から構造層と questions.md を生成する。"""
    from sheetlens.pipeline import ExistingStructureError, extract_workbook

    try:
        proj = extract_workbook(file, out)
    except ExistingStructureError as e:
        typer.echo(str(e))
        raise typer.Exit(1) from e
    except (InvalidFileException, BadZipFile, KeyError) as e:
        typer.echo(f"エラー: {file} を読めません（破損またはパスワード保護の可能性）: {e}")
        raise typer.Exit(1) from e
    typer.echo(f"生成しました: {proj}")


@app.command(name="compile")
def compile_cmd(project: Path) -> None:
    """構造層 + 注釈を統合した Markdown を再生成する。"""
    from sheetlens.annotations.schema import AnnotationError
    from sheetlens.pipeline import compile_project

    raw = project / "structure" / "raw.json"
    if not raw.exists():
        typer.echo(f"エラー: {project} は sheetlens プロジェクトではありません（structure/raw.json がありません）")
        raise typer.Exit(1)
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
    from sheetlens.annotations.schema import AnnotationError, find_orphans, load_annotations
    from sheetlens.model import ir
    from sheetlens.pipeline import analyze, find_unwoven

    raw = project / "structure" / "raw.json"
    if not raw.exists():
        typer.echo(f"エラー: {project} は sheetlens プロジェクトではありません（structure/raw.json がありません）")
        raise typer.Exit(1)
    wb = ir.Workbook.model_validate_json(raw.read_text(encoding="utf-8"))
    try:
        anns = load_annotations(project / "annotations")
    except AnnotationError as e:
        typer.echo(f"注釈エラー: {e}")
        raise typer.Exit(1) from e
    analysis = analyze(wb)
    for o in find_orphans(wb, anns) + find_unwoven(wb, analysis, anns):
        typer.echo(f"警告（孤立注釈）: {o}")
    questions = analysis.questions
    answered = {qid for a in anns for qid in a.questions_answered}
    unanswered = sum(1 for q in questions if q.id not in answered)
    typer.echo(f"未回答質問: {unanswered} / {len(questions)}")
