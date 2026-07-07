from collections.abc import Iterable

from openpyxl.utils import get_column_letter, range_boundaries

from sheetlens.annotations.schema import AnnotationTarget, SheetAnnotations
from sheetlens.detectors.formula_patterns import FormulaPattern
from sheetlens.detectors.questions import Question
from sheetlens.detectors.regions import Region
from sheetlens.model import ir

MAX_GRID_ROWS = 40
MAX_GRID_COLS = 15


def _fmt_target(t: AnnotationTarget) -> str:
    if t.kind == "input_source":
        parts = [f"入力元: {t.value}"] if t.value else []
        if t.by:
            parts.append(f"入力者: {t.by}")
        if t.when:
            parts.append(f"タイミング: {t.when}")
        return " / ".join(parts) or (t.note or "")
    if t.kind == "dropdown_semantics" and t.values:
        return "選択肢の意味: " + "、".join(f"「{k}」={v}" for k, v in t.values.items())
    return t.note or t.value or ""


def _ann_lines(ann: SheetAnnotations | None, rng: str) -> list[str]:
    if not ann:
        return []
    lines = [f"> 💬 業務上の意味: {_fmt_target(t)}" for t in ann.targets if t.range == rng]
    return lines + [""] if lines else []


def _cell_text(text: str) -> str:
    return text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("|", "\\|")


def _grid(sheet: ir.Sheet) -> list[str]:
    if not sheet.cells or not sheet.used_range:
        return ["（空シート）", ""]
    cellmap = {c.ref: c for c in sheet.cells}
    anchors: dict[str, str] = {}
    covered: set[tuple[int, int]] = set()
    for m in sheet.merged:
        min_c, min_r, max_c, max_r = range_boundaries(m)
        anchors[f"{get_column_letter(min_c)}{min_r}"] = m
        covered.update(
            (r, c)
            for r in range(min_r, max_r + 1)
            for c in range(min_c, max_c + 1)
            if (r, c) != (min_r, min_c)
        )
    min_c, min_r, max_c, max_r = range_boundaries(sheet.used_range)
    trunc = max_r - min_r + 1 > MAX_GRID_ROWS or max_c - min_c + 1 > MAX_GRID_COLS
    max_r = min(max_r, min_r + MAX_GRID_ROWS - 1)
    max_c = min(max_c, min_c + MAX_GRID_COLS - 1)
    cols = [get_column_letter(c) for c in range(min_c, max_c + 1)]
    lines = ["| 行 | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for r in range(min_r, max_r + 1):
        row: list[str] = []
        for c in range(min_c, max_c + 1):
            ref = f"{get_column_letter(c)}{r}"
            if (r, c) in covered:
                row.append("←")
                continue
            cell = cellmap.get(ref)
            text = "" if cell is None else str(cell.value if cell.value is not None else cell.formula or "")
            if ref in anchors:
                text = f"[{anchors[ref]} 結合] {text}".strip()
            row.append(_cell_text(text))
        lines.append(f"| {r} | " + " | ".join(row) + " |")
    if trunc:
        lines.append("")
        lines.append(f"（{MAX_GRID_ROWS} 行 × {MAX_GRID_COLS} 列で打ち切り。以降は raw.json を参照）")
    return lines + [""]


def render_sheet_md(
    sheet: ir.Sheet,
    patterns: list[FormulaPattern],
    regions: list[Region],
    questions: list[Question],
    buttons: list[ir.ButtonLink],
    ann: SheetAnnotations | None = None,
    answered: Iterable[str] = frozenset(),
) -> str:
    answered = set(answered)
    lines = [f"# シート: {sheet.name}", ""]
    if ann and ann.role:
        stage = f"（工程: {ann.workflow_stage}）" if ann.workflow_stage else ""
        lines += [f"> 💬 業務上の意味: {ann.role}{stage}", ""]
    flags = []
    if sheet.hidden:
        flags.append("非表示シート")
    if sheet.protected:
        flags.append("保護あり")
    if sheet.hidden_cols:
        flags.append(f"非表示列: {', '.join(sheet.hidden_cols)}")
    lines += [
        "## 概要",
        f"- 使用範囲: {sheet.used_range or 'なし'} / 結合セル: {len(sheet.merged)} 箇所 / "
        f"数式セル: {sum(1 for c in sheet.cells if c.formula)} / 入力規則: {len(sheet.validations)}",
    ]
    if flags:
        lines.append(f"- 属性: {' / '.join(flags)}")
    lines += ["", "## レイアウトマップ", ""]
    lines += _grid(sheet)
    if regions:
        lines += ["## 領域", ""]
        for i, region in enumerate(regions, 1):
            kind = "テーブル" if region.kind == "table" else "ブロック"
            lines.append(f"### 領域{i}: {region.range} — {kind}")
            lines += _ann_lines(ann, region.range)
        lines.append("")
    if patterns:
        lines += ["## 数式（正規化済み）", ""]
        for p in patterns:
            lines.append(f"- {', '.join(p.ranges)} = `{p.pattern}`（例: `{p.example}`）")
            for ex in p.exceptions:
                lines.append(f"  - **⚠ 例外: {ex}**（パターンから逸脱。特例または誤りの可能性）")
        lines.append("")
    if sheet.validations:
        lines += ["## 入力規則（プルダウン等）", ""]
        for v in sheet.validations:
            choices = f" 選択肢: {', '.join(v.choices)}" if v.choices else ""
            lines.append(f"- {', '.join(v.ranges)}: {v.type}（{v.formula1 or ''}）{choices}")
            for rng in v.ranges:
                lines += _ann_lines(ann, rng)
        lines.append("")
    if sheet.conditional_formats:
        lines += ["## 条件付き書式", ""]
        for cf in sheet.conditional_formats:
            cond = " ".join(x for x in (cf.operator, cf.formula) if x) or cf.rule_type
            lines.append(f"- {cf.range}: {cf.rule_type} — 条件: {cond}")
            lines += _ann_lines(ann, cf.range)
        lines.append("")
    if buttons:
        lines += ["## VBA との接続", ""]
        for b in buttons:
            label = f"「{b.label}」" if b.label else ""
            lines.append(f"- ボタン{label} → {b.macro}")
        lines.append("")
    unanswered = [q for q in questions if q.sheet == sheet.name and q.id not in answered]
    if unanswered:
        lines += ["## 未確認事項", ""]
        for q in unanswered:
            lines.append(f"> ❓ 未確認 ({q.id}): [{q.target}] {q.text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_readme(
    wb: ir.Workbook,
    deps: dict[str, list[str]],
    questions: list[Question],
    answered: Iterable[str],
) -> str:
    answered = set(answered)
    lines = [f"# {wb.source_file} — SheetLens 抽出結果", ""]
    if wb.extraction_gaps:
        lines += [f"**⚠ この抽出には {len(wb.extraction_gaps)} 件の欠落があります:**", ""]
        lines += [f"- {g}" for g in wb.extraction_gaps]
        lines.append("")
    lines += [
        "## 読み方",
        "",
        "- `structure/sheet-*.md`: シートごとの構造ビュー（compile 後は業務注釈も織り込み済み）",
        "- `structure/raw.json`: 省略なしの全抽出データ（機械可読の正）",
        "- `structure/vba/*.bas`: VBA ソース",
        "- `annotations/*.yaml`: 業務上の意味（人間の回答。手で編集してよい唯一の場所）",
        "- `questions.md`: 業務担当者に確認すべき質問リスト",
        "",
        "## シート一覧",
        "",
    ]
    for s in wb.sheets:
        mark = "（非表示）" if s.hidden else ""
        lines.append(f"- {s.name}{mark}: 使用範囲 {s.used_range or 'なし'}")
    edges = [(a, bs) for a, bs in deps.items() if bs]
    if edges:
        lines += ["", "## シート間依存（参照する側 → される側）", ""]
        lines += [f"- {a} → {', '.join(bs)}" for a, bs in edges]
    unanswered = sum(1 for q in questions if q.id not in answered)
    lines += ["", f"## 未確認事項: {unanswered} 件（`questions.md` 参照）"]
    return "\n".join(lines).rstrip() + "\n"


def render_questions_md(questions: list[Question], answered: Iterable[str]) -> str:
    answered = set(answered)
    lines = [
        "# 業務担当者への質問リスト",
        "",
        "回答は `annotations/<シート名>.yaml` に記録し、`questions_answered` に ID を追加すること。",
        "",
    ]
    for q in questions:
        mark = "x" if q.id in answered else " "
        lines.append(f"- [{mark}] **{q.id}** [{q.sheet} / {q.target}] ({q.category}) {q.text}")
    return "\n".join(lines).rstrip() + "\n"
