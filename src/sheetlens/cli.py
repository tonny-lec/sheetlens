from pathlib import Path
from typing import TYPE_CHECKING
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException
import typer

if TYPE_CHECKING:
    from sheetlens.question_ids import AnswerResolution

app = typer.Typer(help="業務 Excel を AI が誤読しない中間表現に変換する", no_args_is_help=True)


def _print_question_resolution(
    resolution: "AnswerResolution",
    legacy_source_sha256: str | None,
) -> None:
    for diagnostic in resolution.diagnostics:
        if diagnostic.kind == "changed":
            typer.echo(
                f"警告（質問ID変更）: {diagnostic.question_id} -> {diagnostic.current_id}"
            )
        elif diagnostic.kind == "deleted":
            typer.echo(f"警告（質問ID削除）: {diagnostic.question_id}")
        else:
            typer.echo(f"警告（質問ID未解決）: {diagnostic.question_id}")

    if resolution.legacy_ids:
        typer.echo(f"旧質問 ID を自動解決: {len(resolution.legacy_ids)} 件")
        typer.echo(
            f"legacy_source_sha256: {legacy_source_sha256} "
            "（旧 alias の由来であり、回答時世代そのものを証明しません）"
        )


@app.command()
def extract(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    out: Path | None = typer.Option(None, "-o", "--out"),
) -> None:
    """xlsx/xlsm から構造層と questions.md を生成する。"""
    from sheetlens.detectors.questions import QuestionIdentityError
    from sheetlens.pipeline import ExistingStructureError, extract_workbook
    from sheetlens.question_ids import QuestionCatalogError

    try:
        proj = extract_workbook(file, out)
    except (QuestionCatalogError, QuestionIdentityError) as e:
        typer.echo(f"質問 ID エラー: {e}")
        raise typer.Exit(1) from e
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
    from sheetlens.detectors.questions import QuestionIdentityError
    from sheetlens.pipeline import compile_project
    from sheetlens.question_ids import QuestionCatalogError

    raw = project / "structure" / "raw.json"
    if not raw.exists():
        typer.echo(f"エラー: {project} は sheetlens プロジェクトではありません（structure/raw.json がありません）")
        raise typer.Exit(1)
    try:
        result = compile_project(project)
    except AnnotationError as e:
        typer.echo(f"注釈エラー: {e}")
        raise typer.Exit(1) from e
    except (QuestionCatalogError, QuestionIdentityError) as e:
        typer.echo(f"質問 ID エラー: {e}")
        raise typer.Exit(1) from e
    for warning in result.warnings:
        typer.echo(f"警告（孤立注釈）: {warning}")
    _print_question_resolution(
        result.question_state.resolution,
        result.question_state.catalog.legacy_source_sha256,
    )
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
