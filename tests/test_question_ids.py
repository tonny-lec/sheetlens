import json

import pytest

from sheetlens.detectors import questions
from sheetlens.detectors.questions import Question, QuestionSet
from sheetlens.model import ir
from sheetlens.question_ids import (
    CatalogQuestion,
    QuestionCatalogError,
    QuestionIdCatalog,
    build_catalog,
    is_legacy_question_id,
    legacy_snapshot_matches,
    load_catalog,
    record_unresolved_legacy_ids,
    resolve_answered_ids,
    save_catalog,
    validate_catalog_questions,
)


def _generated_question_set(*sheet_names: str) -> QuestionSet:
    workbook = ir.Workbook(
        source_file="fixture.xlsx",
        sha256="00" * 32,
        sheets=[ir.Sheet(name=name) for name in sheet_names],
    )
    empty = {name: [] for name in sheet_names}
    return questions.generate_question_set(workbook, empty, empty)


def _question_set(*stable_questions: Question, legacy_aliases=None) -> QuestionSet:
    return QuestionSet(
        questions=list(stable_questions),
        legacy_questions=[],
        legacy_aliases=legacy_aliases or {},
    )


def _catalog_fixture() -> QuestionIdCatalog:
    question_set = _generated_question_set("入力", "出力")
    return build_catalog(
        "11" * 32,
        question_set,
        legacy_aliases=question_set.legacy_aliases,
        legacy_source_sha256="22" * 32,
    )


def _changed_question_pair() -> tuple[Question, Question]:
    old = questions._stable_question("sheet_role", "入力", "入力", "sheet_role", "古い質問文")
    current = questions._stable_question("sheet_role", "入力", "入力", "sheet_role", "新しい質問文")
    assert old.identity_sha256 == current.identity_sha256
    assert old.id != current.id
    return old, current


def test_catalog_schema_constants_and_alias_provenance():
    question_set = _generated_question_set("入力")

    catalog = build_catalog(
        "11" * 32,
        question_set,
        legacy_aliases=question_set.legacy_aliases,
        legacy_source_sha256="22" * 32,
    )

    assert catalog.schema_version == 1
    assert catalog.generator_version == 2
    assert catalog.legacy_aliases == question_set.legacy_aliases
    assert catalog.current_ids == [question_set.questions[0].id]


def test_legacy_id_recognizes_minimum_width_not_maximum_width():
    assert is_legacy_question_id("q-999")
    assert is_legacy_question_id("q-1000")
    assert not is_legacy_question_id("q-99")
    assert not is_legacy_question_id("q2-sheet_role-68ae6d6b93515448")


def test_save_catalog_is_deterministic_and_ends_with_newline(tmp_path):
    path = tmp_path / "question-ids.json"
    catalog = _catalog_fixture().model_copy(
        update={
            "current_ids": list(reversed(_catalog_fixture().current_ids)),
            "questions": dict(reversed(list(_catalog_fixture().questions.items()))),
            "legacy_aliases": dict(reversed(list(_catalog_fixture().legacy_aliases.items()))),
            "unresolved_legacy_ids": ["q-1000", "q-999"],
        }
    )

    save_catalog(path, catalog)
    first = path.read_bytes()
    save_catalog(path, catalog)

    assert path.read_bytes() == first
    assert first.endswith(b"\n")
    assert not (tmp_path / ".question-ids.json.tmp").exists()
    payload = json.loads(first)
    assert payload["current_ids"] == sorted(payload["current_ids"])
    assert list(payload["questions"]) == sorted(payload["questions"])
    assert list(payload["legacy_aliases"]) == sorted(payload["legacy_aliases"])
    assert payload["unresolved_legacy_ids"] == ["q-1000", "q-999"]


def test_load_catalog_round_trips_and_checks_expected_source(tmp_path):
    path = tmp_path / "question-ids.json"
    save_catalog(path, _catalog_fixture())

    loaded = load_catalog(path, expected_source_sha256="11" * 32)

    assert loaded == _catalog_fixture()
    assert load_catalog(tmp_path / "missing.json") is None
    with pytest.raises(QuestionCatalogError, match="source_sha256"):
        load_catalog(path, expected_source_sha256="ff" * 32)


@pytest.mark.parametrize("contents", ["{", '{"schema_version": 99}'])
def test_load_catalog_wraps_json_and_schema_errors(tmp_path, contents):
    path = tmp_path / "question-ids.json"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(QuestionCatalogError):
        load_catalog(path)


@pytest.mark.parametrize("field", ["rule", "identity_sha256", "content_sha256"])
def test_build_catalog_rejects_blank_stable_fingerprint_fields(field):
    stable = _generated_question_set("入力").questions[0]
    invalid = stable.model_copy(update={field: ""})

    with pytest.raises(QuestionCatalogError, match=field):
        build_catalog("11" * 32, _question_set(invalid))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"identity_sha256": "f" * 64}, "identity_sha256"),
        ({"content_sha256": "e" * 64}, "content_sha256"),
        ({"text": "改ざんされた文面"}, "question ID"),
    ],
)
def test_load_catalog_rejects_disagreeing_digest_or_canonical_fields(tmp_path, mutation, message):
    path = tmp_path / "question-ids.json"
    save_catalog(path, _catalog_fixture())
    payload = json.loads(path.read_text(encoding="utf-8"))
    question_id = payload["current_ids"][0]
    payload["questions"][question_id].update(mutation)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(QuestionCatalogError, match=message):
        load_catalog(path)


def test_load_catalog_rejects_question_key_that_disagrees_with_recomputed_id(tmp_path):
    path = tmp_path / "question-ids.json"
    save_catalog(path, _catalog_fixture())
    payload = json.loads(path.read_text(encoding="utf-8"))
    question_id = payload["current_ids"][0]
    payload["questions"]["q2-sheet_role-0000000000000000"] = payload["questions"].pop(question_id)
    payload["current_ids"][0] = "q2-sheet_role-0000000000000000"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(QuestionCatalogError, match="question ID"):
        load_catalog(path)


@pytest.mark.parametrize(
    "invalid_state",
    ["invalid-key", "dangling-target", "missing-provenance", "orphaned-provenance"],
)
def test_load_catalog_rejects_invalid_legacy_alias_invariants(tmp_path, invalid_state):
    path = tmp_path / "question-ids.json"
    save_catalog(path, _catalog_fixture())
    payload = json.loads(path.read_text(encoding="utf-8"))

    if invalid_state == "invalid-key":
        target = next(iter(payload["legacy_aliases"].values()))
        payload["legacy_aliases"] = {"legacy-001": target}
    elif invalid_state == "dangling-target":
        alias = next(iter(payload["legacy_aliases"]))
        payload["legacy_aliases"][alias] = "q2-missing-0000000000000000"
    elif invalid_state == "missing-provenance":
        payload["legacy_source_sha256"] = None
    else:
        payload["legacy_aliases"] = {}
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(QuestionCatalogError, match="legacy"):
        load_catalog(path)


def test_build_catalog_rejects_invalid_legacy_alias_key():
    question_set = _generated_question_set("入力")

    with pytest.raises(QuestionCatalogError, match="legacy alias"):
        build_catalog(
            "11" * 32,
            question_set,
            legacy_aliases={"legacy-001": question_set.questions[0].id},
            legacy_source_sha256="22" * 32,
        )


def test_build_catalog_rejects_dangling_legacy_alias_target():
    with pytest.raises(QuestionCatalogError, match="target"):
        build_catalog(
            "11" * 32,
            _generated_question_set("入力"),
            legacy_aliases={"q-001": "q2-missing-0000000000000000"},
            legacy_source_sha256="22" * 32,
        )


def test_build_catalog_rejects_alias_without_legacy_source_provenance():
    question_set = _generated_question_set("入力")

    with pytest.raises(QuestionCatalogError, match="legacy_source_sha256"):
        build_catalog(
            "11" * 32,
            question_set,
            legacy_aliases={"q-001": question_set.questions[0].id},
        )


def test_build_catalog_rejects_legacy_source_without_aliases():
    with pytest.raises(QuestionCatalogError, match="legacy_source_sha256"):
        build_catalog(
            "11" * 32,
            _generated_question_set("入力"),
            legacy_source_sha256="22" * 32,
        )


def test_resolver_rejects_invalid_alias_catalog_before_authorizing_current_id():
    catalog = _catalog_fixture().model_copy(update={"legacy_source_sha256": None})

    with pytest.raises(QuestionCatalogError, match="legacy_source_sha256"):
        resolve_answered_ids([catalog.current_ids[0]], catalog)


def test_validate_catalog_rejects_fresh_question_set_difference_despite_source_match():
    catalog = _catalog_fixture()
    different = _generated_question_set("別シート")

    with pytest.raises(QuestionCatalogError, match="current_ids"):
        validate_catalog_questions(catalog, different)


def test_build_catalog_preserves_history_and_merges_aliases():
    old, current = _changed_question_pair()
    previous = build_catalog(
        "11" * 32,
        _question_set(old),
        legacy_aliases={"q-001": old.id},
        legacy_source_sha256="aa" * 32,
        unresolved_legacy_ids=["q-900"],
    )

    merged = build_catalog(
        "22" * 32,
        _question_set(current),
        previous=previous,
        legacy_aliases={"q-002": current.id, "q-003": old.id},
        unresolved_legacy_ids=["q-901"],
    )

    assert merged.current_ids == [current.id]
    assert set(merged.questions) == {old.id, current.id}
    assert merged.legacy_aliases == {
        "q-001": old.id,
        "q-002": current.id,
        "q-003": old.id,
    }
    assert merged.legacy_source_sha256 == "aa" * 32
    assert merged.unresolved_legacy_ids == ["q-900", "q-901"]


def test_build_catalog_replaces_normalization_only_raw_representation():
    decomposed = questions._stable_question(
        "list_validation",
        "入力",
        "A1 , B2",
        "dropdown_semantics",
        "Cafe\u0301  の   説明",
    )
    canonical = questions._stable_question(
        "list_validation",
        "入力",
        "A1,B2",
        "dropdown_semantics",
        "Café の 説明",
    )
    assert decomposed.id == canonical.id
    assert decomposed.identity_sha256 == canonical.identity_sha256
    assert decomposed.content_sha256 == canonical.content_sha256
    assert (decomposed.target, decomposed.text) != (canonical.target, canonical.text)
    previous = build_catalog("11" * 32, _question_set(decomposed))

    merged = build_catalog("22" * 32, _question_set(canonical), previous=previous)

    assert merged.questions[canonical.id].target == canonical.target
    assert merged.questions[canonical.id].text == canonical.text


def test_build_catalog_rejects_previous_alias_with_different_target():
    old, current = _changed_question_pair()
    previous = build_catalog(
        "11" * 32,
        _question_set(old),
        legacy_aliases={"q-001": old.id},
        legacy_source_sha256="aa" * 32,
    )

    with pytest.raises(QuestionCatalogError, match="q-001"):
        build_catalog(
            "22" * 32,
            _question_set(current),
            previous=previous,
            legacy_aliases={"q-001": current.id},
        )


def test_build_catalog_rejects_changed_previous_legacy_source():
    question_set = _generated_question_set("入力")
    previous = build_catalog(
        "11" * 32,
        question_set,
        legacy_aliases={"q-001": question_set.questions[0].id},
        legacy_source_sha256="aa" * 32,
    )

    with pytest.raises(QuestionCatalogError, match="legacy_source_sha256"):
        build_catalog(
            "22" * 32,
            _generated_question_set("入力"),
            previous=previous,
            legacy_source_sha256="bb" * 32,
        )


def test_resolve_answered_ids_classifies_current_and_legacy_alias():
    catalog = _catalog_fixture()
    current = catalog.current_ids[0]
    legacy = next(source for source, target in catalog.legacy_aliases.items() if target == current)

    result = resolve_answered_ids([current, legacy], catalog)

    assert result.answered_ids == {current}
    assert result.legacy_ids == [legacy]
    assert result.diagnostics == []


def test_resolve_answered_ids_classifies_changed_historical_id():
    old, current = _changed_question_pair()
    previous = build_catalog("11" * 32, _question_set(old))
    catalog = build_catalog("22" * 32, _question_set(current), previous=previous)

    result = resolve_answered_ids([old.id], catalog)

    assert result.answered_ids == set()
    assert [diagnostic.model_dump() for diagnostic in result.diagnostics] == [
        {"kind": "changed", "question_id": old.id, "current_id": current.id}
    ]


def test_resolve_answered_ids_classifies_deleted_historical_id():
    old = questions._stable_question("sheet_role", "削除", "削除", "sheet_role", "古い")
    current = questions._stable_question("sheet_role", "現行", "現行", "sheet_role", "新しい")
    previous = build_catalog("11" * 32, _question_set(old))
    catalog = build_catalog("22" * 32, _question_set(current), previous=previous)

    result = resolve_answered_ids([old.id], catalog)

    assert result.answered_ids == set()
    assert [diagnostic.model_dump() for diagnostic in result.diagnostics] == [
        {"kind": "deleted", "question_id": old.id, "current_id": None}
    ]


def test_resolve_answered_ids_classifies_unknown_stable_and_legacy_ids():
    catalog = _catalog_fixture()

    result = resolve_answered_ids(["q2-unknown-0000000000000000", "q-999"], catalog)

    assert result.answered_ids == set()
    assert result.legacy_ids == []
    assert [diagnostic.model_dump() for diagnostic in result.diagnostics] == [
        {
            "kind": "unresolved",
            "question_id": "q2-unknown-0000000000000000",
            "current_id": None,
        },
        {"kind": "unresolved", "question_id": "q-999", "current_id": None},
    ]


@pytest.mark.parametrize(
    ("same_identity", "expected_kind"), [(True, "changed"), (False, "deleted")]
)
def test_legacy_alias_to_historical_id_is_expanded_before_classification(
    same_identity, expected_kind
):
    old, changed = _changed_question_pair()
    current = (
        changed
        if same_identity
        else questions._stable_question(
            "sheet_role", "別シート", "別シート", "sheet_role", "別の質問"
        )
    )
    previous = build_catalog(
        "11" * 32,
        _question_set(old),
        legacy_aliases={"q-001": old.id},
        legacy_source_sha256="aa" * 32,
    )
    catalog = build_catalog("22" * 32, _question_set(current), previous=previous)

    result = resolve_answered_ids(["q-001"], catalog)

    assert result.answered_ids == set()
    assert result.legacy_ids == []
    diagnostic = result.diagnostics[0]
    assert diagnostic.kind == expected_kind
    assert diagnostic.question_id == "q-001"
    assert diagnostic.current_id == (current.id if same_identity else None)


def test_resolver_rejects_catalog_current_id_missing_from_questions():
    catalog = _catalog_fixture().model_copy(update={"questions": {}})

    with pytest.raises(QuestionCatalogError, match="current ID"):
        resolve_answered_ids([], catalog)


def test_legacy_snapshot_matches_only_normalizes_question_checkboxes():
    existing = "# Header\n- [x] **q-001** question\n- [ ] ordinary task\n"
    expected = "# Header\n- [ ] **q-001** question\n- [ ] ordinary task\n"
    changed_non_question = "# Header\n- [ ] **q-001** question\n- [x] ordinary task\n"

    assert legacy_snapshot_matches(existing, expected)
    assert not legacy_snapshot_matches(existing, changed_non_question)
    assert not legacy_snapshot_matches(existing + "extra\n", expected)


def test_record_unresolved_legacy_ids_returns_sorted_validated_copy():
    catalog = _catalog_fixture().model_copy(update={"unresolved_legacy_ids": ["q-900"]})
    original_aliases = dict(catalog.legacy_aliases)

    updated = record_unresolved_legacy_ids(catalog, ["q-1000", "q-999", "q-900"])

    assert updated is not catalog
    assert updated.unresolved_legacy_ids == ["q-1000", "q-900", "q-999"]
    assert updated.legacy_aliases == original_aliases
    assert catalog.unresolved_legacy_ids == ["q-900"]


def test_record_unresolved_legacy_ids_rejects_invalid_iterable_values():
    with pytest.raises(QuestionCatalogError, match="unresolved_legacy_ids"):
        record_unresolved_legacy_ids(_catalog_fixture(), [None])


def test_catalog_models_forbid_unknown_fields():
    question = next(iter(_catalog_fixture().questions.values()))

    with pytest.raises(Exception):
        CatalogQuestion.model_validate({**question.model_dump(), "unknown": True})
    with pytest.raises(Exception):
        QuestionIdCatalog.model_validate({**_catalog_fixture().model_dump(), "unknown": True})
