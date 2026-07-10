import pytest

from sheetlens.detectors import questions
from sheetlens.detectors.regions import Region
from sheetlens.model import ir


def _by_key(questions, sheet, category, target):
    return next(
        q for q in questions
        if (q.sheet, q.category, q.target) == (sheet, category, target)
    )


def test_rules_produce_expected_categories():
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="入力",
                used_range="A1:F30",
                hidden_cols=["D"],
                cells=[ir.Cell(ref="A3", value="顧客名"), ir.Cell(ref="E11", formula="=C11*D11")],
                validations=[ir.ValidationRule(ranges=["C5"], type="list", choices=["通常", "特急"])],
                conditional_formats=[ir.ConditionalFormat(range="F11:F30", rule_type="cellIs", operator="lessThan", formula="0")],
            )
        ],
        vba_modules=[ir.VbaModule(name="Sheet1.cls", code="Private Sub Worksheet_Change(ByVal Target As Range)\nEnd Sub")],
        buttons=[ir.ButtonLink(sheet="入力", macro="Module1.Register")],
    )
    regions = {"入力": [Region(range="A3:B8", kind="block"), Region(range="A10:F30", kind="table")]}
    qs = questions.generate_questions(wb, regions, {"入力": []})
    cats = {q.category for q in qs}
    assert cats == {"sheet_role", "input_source", "dropdown_semantics", "alert_action", "trigger_timing", "hidden_reason"}
    assert [(q.category, q.target, q.rule) for q in qs] == [
        ("sheet_role", "入力", "sheet_role"),
        ("hidden_reason", "D", "hidden_columns"),
        ("input_source", "A3:B8", "input_region"),
        ("dropdown_semantics", "C5", "list_validation"),
        ("alert_action", "F11:F30", "conditional_format"),
        ("trigger_timing", "Module1.Register", "button_macro"),
        ("trigger_timing", "Sheet1.cls.Worksheet_Change", "vba_event"),
    ]
    assert all(q.id.startswith(f"q2-{q.rule}-") for q in qs)
    assert all(len(q.identity_sha256) == 64 for q in qs)
    assert all(len(q.content_sha256) == 64 for q in qs)
    # A3:B8 は数式を含まないので input_source、A10:F30 は E11 の数式を含むので対象外
    targets = [q.target for q in qs if q.category == "input_source"]
    assert targets == ["A3:B8"]


def test_sheet_role_id_is_a_stable_golden_value():
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[ir.Sheet(name="入力")],
    )
    question = questions.generate_questions(wb, {"入力": []}, {"入力": []})[0]
    assert question.id == "q2-sheet_role-68ae6d6b93515448"
    assert question.rule == "sheet_role"
    assert question.identity_sha256 == (
        "e4b1b4c9098f32ec7d8eea00187a1eb0acd3b483143f8870c069f8bd30a7176a"
    )
    assert question.content_sha256 == (
        "68ae6d6b935154481ae9999f9eb2597da087c01b6d9e97706e178ba054003a49"
    )


def test_existing_ids_survive_questions_inserted_before_them():
    base = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[ir.Sheet(name="入力")],
    )
    expanded = ir.Workbook(
        source_file="b.xlsx",
        sha256="11" * 32,
        sheets=[
            ir.Sheet(name="表紙", hidden=True),
            ir.Sheet(
                name="入力",
                validations=[
                    ir.ValidationRule(ranges=["C5"], type="list", choices=["通常", "特急"])
                ],
            ),
        ],
    )
    base_id = _by_key(
        questions.generate_questions(base, {"入力": []}, {"入力": []}),
        "入力", "sheet_role", "入力",
    ).id
    expanded_id = _by_key(
        questions.generate_questions(
            expanded,
            {"表紙": [], "入力": []},
            {"表紙": [], "入力": []},
        ),
        "入力", "sheet_role", "入力",
    ).id
    assert expanded_id == base_id


def test_hidden_and_protected_sheet_questions_have_distinct_rule_ids():
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[ir.Sheet(name="機密", hidden=True, protected=True)],
    )

    hidden_questions = [
        q for q in questions.generate_questions(wb, {"機密": []}, {"機密": []})
        if q.category == "hidden_reason"
    ]

    assert {q.rule for q in hidden_questions} == {"hidden_sheet", "protected_sheet"}
    assert len({q.id for q in hidden_questions}) == 2


def test_nfc_equivalent_text_and_comma_spacing_have_same_digests():
    spaced = questions._stable_question(
        "list_validation", "入力", "A1 , B2", "dropdown_semantics", "Cafe\u0301  の   説明"
    )
    canonical = questions._stable_question(
        "list_validation", "入力", "A1,B2", "dropdown_semantics", "Café の 説明"
    )

    assert spaced.identity_sha256 == canonical.identity_sha256
    assert spaced.content_sha256 == canonical.content_sha256
    assert spaced.id == canonical.id


def test_meaningful_sheet_whitespace_is_not_collapsed():
    single_space = questions._stable_question(
        "sheet_role", "入力 表", "入力", "sheet_role", "説明"
    )
    double_space = questions._stable_question(
        "sheet_role", "入力  表", "入力", "sheet_role", "説明"
    )

    assert single_space.identity_sha256 != double_space.identity_sha256
    assert single_space.content_sha256 != double_space.content_sha256
    assert single_space.id != double_space.id


def test_duplicate_buttons_collapse_but_keep_legacy_aliases():
    wb = ir.Workbook(
        source_file="a.xlsm",
        sha256="00" * 32,
        buttons=[
            ir.ButtonLink(sheet="入力", macro="Module1.Register"),
            ir.ButtonLink(sheet="入力", macro="Module1.Register"),
        ],
    )

    result = questions.generate_question_set(wb, {}, {})

    assert len(result.questions) == 1
    assert [q.id for q in result.legacy_questions] == ["q-001", "q-002"]
    assert result.legacy_aliases == {
        "q-001": result.questions[0].id,
        "q-002": result.questions[0].id,
    }


def test_truncated_digest_collision_raises(monkeypatch):
    monkeypatch.setattr(
        questions,
        "_short_question_id",
        lambda rule, content_sha256: "q2-collision-deadbeefdeadbeef",
        raising=False,
    )
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[ir.Sheet(name="入力"), ir.Sheet(name="出力")],
    )

    with pytest.raises(questions.QuestionIdentityError, match="digest が衝突"):
        questions.generate_questions(
            wb,
            {"入力": [], "出力": []},
            {"入力": [], "出力": []},
        )
