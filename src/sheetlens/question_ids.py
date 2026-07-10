from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from sheetlens.detectors.questions import Question, QuestionSet, _stable_question


_LEGACY_QUESTION_ID_RE = re.compile(r"^q-[0-9]{3,}$")
_QUESTION_CHECKBOX_RE = re.compile(r"^- \[[ x]\] (?=\*\*)", re.MULTILINE)


class CatalogQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: str
    sheet: str
    category: str
    target: str
    text: str
    identity_sha256: str
    content_sha256: str


class QuestionIdCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    generator_version: Literal[2] = 2
    source_sha256: str
    legacy_source_sha256: str | None = None
    current_ids: list[str]
    questions: dict[str, CatalogQuestion]
    legacy_aliases: dict[str, str] = Field(default_factory=dict)
    unresolved_legacy_ids: list[str] = Field(default_factory=list)


class QuestionIdDiagnostic(BaseModel):
    kind: Literal["changed", "deleted", "unresolved"]
    question_id: str
    current_id: str | None = None


class AnswerResolution(BaseModel):
    answered_ids: set[str] = Field(default_factory=set)
    legacy_ids: list[str] = Field(default_factory=list)
    diagnostics: list[QuestionIdDiagnostic] = Field(default_factory=list)


class QuestionCatalogError(ValueError):
    pass


def _catalog_question(question: Question) -> CatalogQuestion:
    for field in ("rule", "identity_sha256", "content_sha256"):
        if not getattr(question, field):
            raise QuestionCatalogError(f"question {question.id!r} has blank {field}")

    canonical = _stable_question(
        question.rule,
        question.sheet,
        question.target,
        question.category,
        question.text,
    )
    if question.id != canonical.id:
        raise QuestionCatalogError(
            f"question ID {question.id!r} disagrees with canonical question ID {canonical.id!r}"
        )
    if question.identity_sha256 != canonical.identity_sha256:
        raise QuestionCatalogError(f"question {question.id!r} has invalid identity_sha256")
    if question.content_sha256 != canonical.content_sha256:
        raise QuestionCatalogError(f"question {question.id!r} has invalid content_sha256")
    return CatalogQuestion(
        rule=question.rule,
        sheet=question.sheet,
        category=question.category,
        target=question.target,
        text=question.text,
        identity_sha256=question.identity_sha256,
        content_sha256=question.content_sha256,
    )


def _validate_question_set(question_set: QuestionSet) -> dict[str, CatalogQuestion]:
    entries: dict[str, CatalogQuestion] = {}
    by_identity: dict[str, str] = {}
    for question in question_set.questions:
        entry = _catalog_question(question)
        if question.id in entries and entries[question.id] != entry:
            raise QuestionCatalogError(
                f"duplicate question ID has different content: {question.id}"
            )
        prior_id = by_identity.get(entry.identity_sha256)
        if prior_id is not None and prior_id != question.id:
            raise QuestionCatalogError(
                f"multiple current questions share identity_sha256: {prior_id}, {question.id}"
            )
        entries[question.id] = entry
        by_identity[entry.identity_sha256] = question.id
    return entries


def _validate_catalog(catalog: QuestionIdCatalog) -> None:
    if len(catalog.current_ids) != len(set(catalog.current_ids)):
        raise QuestionCatalogError("catalog current_ids contains duplicates")

    has_legacy_aliases = bool(catalog.legacy_aliases)
    has_legacy_source = catalog.legacy_source_sha256 is not None
    if has_legacy_aliases and not has_legacy_source:
        raise QuestionCatalogError(
            "catalog legacy_aliases require a non-null legacy_source_sha256"
        )
    if has_legacy_source and not has_legacy_aliases:
        raise QuestionCatalogError(
            "catalog legacy_source_sha256 requires at least one legacy alias"
        )

    for question_id, entry in catalog.questions.items():
        question = Question(id=question_id, **entry.model_dump())
        _catalog_question(question)

    current_by_identity: dict[str, str] = {}
    for question_id in catalog.current_ids:
        entry = catalog.questions.get(question_id)
        if entry is None:
            raise QuestionCatalogError(
                f"catalog current ID is missing from questions: {question_id}"
            )
        prior_id = current_by_identity.get(entry.identity_sha256)
        if prior_id is not None and prior_id != question_id:
            raise QuestionCatalogError(
                f"multiple current questions share identity_sha256: {prior_id}, {question_id}"
            )
        current_by_identity[entry.identity_sha256] = question_id

    for legacy_id, target in catalog.legacy_aliases.items():
        if not is_legacy_question_id(legacy_id):
            raise QuestionCatalogError(f"invalid legacy alias key: {legacy_id}")
        if target not in catalog.questions:
            raise QuestionCatalogError(
                f"legacy alias target is missing from catalog questions: {legacy_id} -> {target}"
            )


def is_legacy_question_id(question_id: str) -> bool:
    return _LEGACY_QUESTION_ID_RE.fullmatch(question_id) is not None


def build_catalog(
    source_sha256: str,
    question_set: QuestionSet,
    *,
    previous: QuestionIdCatalog | None = None,
    legacy_aliases: Mapping[str, str] | None = None,
    legacy_source_sha256: str | None = None,
    unresolved_legacy_ids: Iterable[str] = (),
) -> QuestionIdCatalog:
    current_questions = _validate_question_set(question_set)

    historical_questions: dict[str, CatalogQuestion] = {}
    merged_aliases: dict[str, str] = {}
    previous_unresolved: list[str] = []
    preserved_legacy_source = legacy_source_sha256
    if previous is not None:
        _validate_catalog(previous)
        historical_questions.update(previous.questions)
        merged_aliases.update(previous.legacy_aliases)
        previous_unresolved = previous.unresolved_legacy_ids
        preserved_legacy_source = previous.legacy_source_sha256
        if (
            legacy_source_sha256 is not None
            and legacy_source_sha256 != previous.legacy_source_sha256
        ):
            raise QuestionCatalogError("legacy_source_sha256 cannot change while merging a catalog")

    for question_id, entry in current_questions.items():
        prior = historical_questions.get(question_id)
        if prior is not None and (
            prior.identity_sha256 != entry.identity_sha256
            or prior.content_sha256 != entry.content_sha256
        ):
            raise QuestionCatalogError(
                f"historical question ID has different canonical content: {question_id}"
            )
        historical_questions[question_id] = entry

    for legacy_id, target in (legacy_aliases or {}).items():
        prior_target = merged_aliases.get(legacy_id)
        if prior_target is not None and prior_target != target:
            raise QuestionCatalogError(
                f"legacy alias {legacy_id!r} cannot change from {prior_target!r} to {target!r}"
            )
        merged_aliases[legacy_id] = target

    catalog = QuestionIdCatalog(
        source_sha256=source_sha256,
        legacy_source_sha256=preserved_legacy_source,
        current_ids=sorted(current_questions),
        questions=dict(sorted(historical_questions.items())),
        legacy_aliases=dict(sorted(merged_aliases.items())),
        unresolved_legacy_ids=sorted(set(previous_unresolved).union(unresolved_legacy_ids)),
    )
    _validate_catalog(catalog)
    validate_catalog_questions(catalog, question_set)
    return catalog


def load_catalog(
    path: Path,
    *,
    expected_source_sha256: str | None = None,
) -> QuestionIdCatalog | None:
    if not path.exists():
        return None
    try:
        catalog = QuestionIdCatalog.model_validate_json(path.read_text(encoding="utf-8"))
        _validate_catalog(catalog)
    except QuestionCatalogError:
        raise
    except (OSError, UnicodeError, ValidationError, ValueError) as exc:
        raise QuestionCatalogError(f"failed to load question catalog {path}: {exc}") from exc

    if expected_source_sha256 is not None and catalog.source_sha256 != expected_source_sha256:
        raise QuestionCatalogError("catalog source_sha256 does not match expected source_sha256")
    return catalog


def _sorted_catalog(catalog: QuestionIdCatalog) -> QuestionIdCatalog:
    return catalog.model_copy(
        update={
            "current_ids": sorted(catalog.current_ids),
            "questions": dict(sorted(catalog.questions.items())),
            "legacy_aliases": dict(sorted(catalog.legacy_aliases.items())),
            "unresolved_legacy_ids": sorted(catalog.unresolved_legacy_ids),
        }
    )


def save_catalog(path: Path, catalog: QuestionIdCatalog) -> None:
    _validate_catalog(catalog)
    serialized = _sorted_catalog(catalog).model_dump_json(indent=2) + "\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def legacy_snapshot_matches(existing: str, expected: str) -> bool:
    def normalized(value: str) -> str:
        return _QUESTION_CHECKBOX_RE.sub("- [ ] ", value)

    return normalized(existing) == normalized(expected)


def resolve_answered_ids(
    answered_ids: Iterable[str],
    catalog: QuestionIdCatalog,
) -> AnswerResolution:
    _validate_catalog(catalog)
    current_ids = set(catalog.current_ids)
    current_by_identity = {
        catalog.questions[question_id].identity_sha256: question_id
        for question_id in catalog.current_ids
    }
    resolution = AnswerResolution()

    for source_id in answered_ids:
        target_id = source_id
        legacy_source = is_legacy_question_id(source_id)
        if legacy_source:
            target_id = catalog.legacy_aliases.get(source_id, source_id)

        if target_id in current_ids:
            resolution.answered_ids.add(target_id)
            if legacy_source:
                resolution.legacy_ids.append(source_id)
            continue

        historical = catalog.questions.get(target_id)
        if historical is None:
            resolution.diagnostics.append(
                QuestionIdDiagnostic(kind="unresolved", question_id=source_id)
            )
            continue

        current_id = current_by_identity.get(historical.identity_sha256)
        if current_id is None:
            resolution.diagnostics.append(
                QuestionIdDiagnostic(kind="deleted", question_id=source_id)
            )
        else:
            resolution.diagnostics.append(
                QuestionIdDiagnostic(
                    kind="changed",
                    question_id=source_id,
                    current_id=current_id,
                )
            )
    return resolution


def validate_catalog_questions(
    catalog: QuestionIdCatalog,
    question_set: QuestionSet,
) -> None:
    _validate_catalog(catalog)
    expected = _validate_question_set(question_set)
    if set(catalog.current_ids) != set(expected):
        raise QuestionCatalogError("catalog current_ids differ from freshly generated questions")
    for question_id, entry in expected.items():
        if catalog.questions[question_id] != entry:
            raise QuestionCatalogError(
                f"catalog current question differs from freshly generated question: {question_id}"
            )


def record_unresolved_legacy_ids(
    catalog: QuestionIdCatalog,
    question_ids: Iterable[str],
) -> QuestionIdCatalog:
    _validate_catalog(catalog)
    payload = catalog.model_dump()
    payload["unresolved_legacy_ids"] = [*catalog.unresolved_legacy_ids, *question_ids]
    try:
        candidate = QuestionIdCatalog.model_validate(payload)
    except ValidationError as exc:
        raise QuestionCatalogError(f"invalid unresolved_legacy_ids: {exc}") from exc

    payload = candidate.model_dump()
    payload["unresolved_legacy_ids"] = sorted(set(candidate.unresolved_legacy_ids))
    updated = QuestionIdCatalog.model_validate(payload)
    _validate_catalog(updated)
    return updated
