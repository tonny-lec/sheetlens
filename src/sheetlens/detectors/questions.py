import re

from openpyxl.utils import coordinate_to_tuple, range_boundaries
from pydantic import BaseModel

from sheetlens.detectors.formula_patterns import FormulaPattern
from sheetlens.detectors.regions import Region
from sheetlens.model import ir

_EVENT_RE = re.compile(r"^\s*(?:Public\s+|Private\s+)?Sub\s+((?:Worksheet_|Workbook_)\w+)", re.M)


class Question(BaseModel):
    id: str
    sheet: str
    target: str
    category: str
    text: str


def _contains_formula(sheet: ir.Sheet, rng: str) -> bool:
    min_c, min_r, max_c, max_r = range_boundaries(rng)
    for cell in sheet.cells:
        if cell.formula is None:
            continue
        r, c = coordinate_to_tuple(cell.ref)
        if min_r <= r <= max_r and min_c <= c <= max_c:
            return True
    return False


def generate_questions(
    wb: ir.Workbook,
    regions: dict[str, list[Region]],
    patterns: dict[str, list[FormulaPattern]],
) -> list[Question]:
    qs: list[Question] = []

    def add(sheet: str, target: str, category: str, text: str) -> None:
        qs.append(Question(id=f"q-{len(qs) + 1:03d}", sheet=sheet, target=target, category=category, text=text))

    for sheet in wb.sheets:
        add(sheet.name, sheet.name, "sheet_role",
            f"シート「{sheet.name}」の役割は何ですか？業務フローのどの工程で使いますか？")
        if sheet.hidden:
            add(sheet.name, sheet.name, "hidden_reason", "このシートはなぜ非表示になっていますか？")
        if sheet.protected:
            add(sheet.name, sheet.name, "hidden_reason", "このシートはなぜ保護されていますか？")
        if sheet.hidden_cols:
            add(sheet.name, ",".join(sheet.hidden_cols), "hidden_reason",
                f"非表示の列（{', '.join(sheet.hidden_cols)}）には何が入っており、なぜ隠されていますか？")
        for region in regions.get(sheet.name, []):
            if not _contains_formula(sheet, region.range):
                add(sheet.name, region.range, "input_source",
                    f"範囲 {region.range} のデータは誰が・いつ・何を見て入力しますか？"
                    "（手入力 / 他システムからの貼り付け / VBA 自動入力）")
        for v in sheet.validations:
            if v.type != "list":
                continue
            label = "、".join(v.choices) if v.choices else (v.formula1 or "参照先リスト")
            add(sheet.name, ",".join(v.ranges), "dropdown_semantics",
                f"プルダウン（{', '.join(v.ranges)}）の選択肢「{label}」はそれぞれ業務上何を意味し、"
                "選択によって後続の処理・判断はどう変わりますか？")
        for cf in sheet.conditional_formats:
            add(sheet.name, cf.range, "alert_action",
                f"範囲 {cf.range} が条件付き書式で強調表示されたとき、業務担当者は何をしますか？")
    for b in wb.buttons:
        add(b.sheet, b.macro, "trigger_timing",
            f"ボタン（マクロ {b.macro}）はどの業務タイミングで押しますか？押す前提条件はありますか？")
    for m in wb.vba_modules:
        for ev in _EVENT_RE.findall(m.code):
            add("(VBA)", f"{m.name}.{ev}", "trigger_timing",
                f"イベントプロシージャ {ev} は業務上どんな操作で発火し、何を自動化していますか？")
    return qs
