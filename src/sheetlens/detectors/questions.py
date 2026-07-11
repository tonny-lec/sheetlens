import hashlib
import json
import re
import unicodedata

from pydantic import BaseModel

from sheetlens.detectors.formula_patterns import FormulaPattern
from sheetlens.detectors.regions import Region, input_ranges
from sheetlens.model import ir

_EVENT_RE = re.compile(r"^\s*(?:Public\s+|Private\s+)?Sub\s+((?:Worksheet_|Workbook_)\w+)", re.M)


class QuestionIdentityError(ValueError):
    pass


class Question(BaseModel):
    id: str
    sheet: str
    target: str
    category: str
    text: str
    rule: str = ""
    identity_sha256: str = ""
    content_sha256: str = ""


class QuestionSet(BaseModel):
    questions: list[Question]
    legacy_questions: list[Question]
    legacy_aliases: dict[str, str]


def _canonical_sha256(value: dict[str, str]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _short_question_id(rule: str, content_sha256: str) -> str:
    return f"q2-{rule}-{content_sha256[:16]}"


def _stable_question(
    rule: str,
    sheet: str,
    target: str,
    category: str,
    text: str,
) -> Question:
    canonical_rule = unicodedata.normalize("NFC", rule)
    canonical_sheet = unicodedata.normalize("NFC", sheet)
    canonical_target = re.sub(r"\s*,\s*", ",", unicodedata.normalize("NFC", target))
    canonical_category = unicodedata.normalize("NFC", category)
    canonical_text = re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()
    identity = {
        "rule": canonical_rule,
        "sheet": canonical_sheet,
        "target": canonical_target,
        "category": canonical_category,
    }
    identity_sha256 = _canonical_sha256(identity)
    content_sha256 = _canonical_sha256({**identity, "text": canonical_text})
    return Question(
        id=_short_question_id(canonical_rule, content_sha256),
        sheet=sheet,
        target=target,
        category=category,
        text=text,
        rule=rule,
        identity_sha256=identity_sha256,
        content_sha256=content_sha256,
    )


def generate_question_set(
    wb: ir.Workbook,
    regions: dict[str, list[Region]],
    patterns: dict[str, list[FormulaPattern]],
) -> QuestionSet:
    questions: list[Question] = []
    legacy_questions: list[Question] = []
    legacy_aliases: dict[str, str] = {}
    by_identity: dict[str, Question] = {}
    by_short_id: dict[str, str] = {}

    def add(rule: str, sheet: str, target: str, category: str, text: str) -> None:
        question = _stable_question(rule, sheet, target, category, text)
        legacy_id = f"q-{len(legacy_questions) + 1:03d}"
        legacy_questions.append(question.model_copy(update={"id": legacy_id}))
        legacy_aliases[legacy_id] = question.id

        prior = by_identity.get(question.identity_sha256)
        if prior is not None:
            if prior.content_sha256 != question.content_sha256:
                raise QuestionIdentityError(
                    f"同じ identity に異なる質問があります: {sheet}/{category}/{target}"
                )
            return
        prior_digest = by_short_id.get(question.id)
        if prior_digest is not None and prior_digest != question.content_sha256:
            raise QuestionIdentityError(f"質問 ID digest が衝突しました: {question.id}")
        by_identity[question.identity_sha256] = question
        by_short_id[question.id] = question.content_sha256
        questions.append(question)

    for sheet in wb.sheets:
        add("sheet_role", sheet.name, sheet.name, "sheet_role",
            f"シート「{sheet.name}」の役割は何ですか？業務フローのどの工程で使いますか？")
        if sheet.hidden:
            add("hidden_sheet", sheet.name, sheet.name, "hidden_reason", "このシートはなぜ非表示になっていますか？")
        if sheet.protected:
            add("protected_sheet", sheet.name, sheet.name, "hidden_reason", "このシートはなぜ保護されていますか？")
        if sheet.hidden_cols:
            add("hidden_columns", sheet.name, ",".join(sheet.hidden_cols), "hidden_reason",
                f"非表示の列（{', '.join(sheet.hidden_cols)}）には何が入っており、なぜ隠されていますか？")
        for region in regions.get(sheet.name, []):
            for target in input_ranges(sheet, region):
                add("input_region", sheet.name, target, "input_source",
                    f"範囲 {target} のデータは誰が・いつ・何を見て入力しますか？"
                    "（手入力 / 他システムからの貼り付け / VBA 自動入力）")
        for v in sheet.validations:
            if v.type != "list":
                continue
            label = "、".join(v.choices) if v.choices else (v.formula1 or "参照先リスト")
            add("list_validation", sheet.name, ",".join(v.ranges), "dropdown_semantics",
                f"プルダウン（{', '.join(v.ranges)}）の選択肢「{label}」はそれぞれ業務上何を意味し、"
                "選択によって後続の処理・判断はどう変わりますか？")
        for cf in sheet.conditional_formats:
            add("conditional_format", sheet.name, cf.range, "alert_action",
                f"範囲 {cf.range} が条件付き書式で強調表示されたとき、業務担当者は何をしますか？")
    for b in wb.buttons:
        add("button_macro", b.sheet, b.macro, "trigger_timing",
            f"ボタン（マクロ {b.macro}）はどの業務タイミングで押しますか？押す前提条件はありますか？")
    for m in wb.vba_modules:
        for ev in _EVENT_RE.findall(m.code):
            add("vba_event", "(VBA)", f"{m.name}.{ev}", "trigger_timing",
                f"イベントプロシージャ {ev} は業務上どんな操作で発火し、何を自動化していますか？")
    return QuestionSet(
        questions=questions,
        legacy_questions=legacy_questions,
        legacy_aliases=legacy_aliases,
    )


def generate_questions(
    wb: ir.Workbook,
    regions: dict[str, list[Region]],
    patterns: dict[str, list[FormulaPattern]],
) -> list[Question]:
    return generate_question_set(wb, regions, patterns).questions
