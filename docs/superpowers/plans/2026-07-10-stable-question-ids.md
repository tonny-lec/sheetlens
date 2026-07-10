# Stable Question IDs and Legacy Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 質問を意味と内容から決定的に識別し、既存 `q-NNN` 回答を annotation YAML の書換えなしで安全に自動解決する。

**Architecture:** 質問生成を rule-aware な candidate pipeline に変え、stable questions、旧表示質問、legacy alias を同時生成する。プロジェクト直下の versioned `question-ids.json` が current/history/alias を保持し、共通 resolver を `extract`、`compile`、`check` から利用する。

**Tech Stack:** Python 3.12、Pydantic v2、Typer、pytest、SHA-256、JSON、openpyxl IR

## Global Constraints

- stable ID は `q2-<rule>-<SHA-256 先頭16hex>` とし、旧 ID は `^q-[0-9]{3,}$` で判定する。
- identity は正規化した `rule/sheet/category/target`、content は identity と正規化した `text` から作る。
- annotation YAML は byte-for-byte で変更しない。
- 一度確定した legacy alias と `legacy_source_sha256` は再抽出後も変更しない。
- `check` は `question-ids.json` を作成・更新しない。
- catalog と `raw.json` の `Workbook.sha256` が不一致なら、既存出力を削除する前に終了コード 1 で停止する。
- 完全重複質問だけをまとめ、同一 identity の異なる content と短縮 digest 衝突はエラーにする。
- wrong-sheet 回答検証、annotation schema 刷新、質問カテゴリ追加、プロジェクト全体の transaction 化は行わない。

---

## File Structure

- Modify `src/sheetlens/detectors/questions.py`: canonicalization、stable ID、candidate dedup、legacy alias を生成する。
- Create `src/sheetlens/question_ids.py`: catalog model、決定的/atomic JSON I/O、history merge、snapshot guard、answer resolver。
- Modify `src/sheetlens/pipeline.py`: catalog lifecycle を `analyze`、`extract`、`compile` に統合する。
- Modify `src/sheetlens/cli.py`: catalog error、legacy 自動解決、changed/deleted/unresolved の出力を統一する。
- Modify `src/sheetlens/renderers/markdown.py`: 生成 README に `question-ids.json` と stable ID の説明を追加する。
- Modify `README.md`: 出力構成と legacy 自動解決の制約を説明する。
- Modify `tests/test_questions.py`: stable ID、前方追加、正規化、重複検査。
- Create `tests/test_question_ids.py`: catalog と resolver の pure unit tests。
- Modify `tests/test_extract_e2e.py`: 初回 migration、再抽出、alias 継承、YAML 不変。
- Modify `tests/test_compile_e2e.py`: legacy 自動解決、snapshot 不一致、catalog 初回保存。
- Modify `tests/test_check_e2e.py`: read-only、changed/deleted/unresolved、catalog errors。
- Modify `tests/test_markdown.py`: 出力 README の catalog 説明を固定する。
- Modify `docs/project/items/SL-001-stable-question-ids.md`: 計画リンク、完了条件、証拠、最終状態。
- Regenerate `docs/project/backlog.md`: SL-001 の最終状態を反映する。

---

### Task 1: Rule-aware stable question generation

**Files:**
- Modify: `src/sheetlens/detectors/questions.py:1-74`
- Modify: `tests/test_questions.py:1-37`

**Interfaces:**
- Produces: `QuestionSet(questions, legacy_questions, legacy_aliases)`
- Produces: `generate_question_set(wb, regions, patterns) -> QuestionSet`
- Preserves: `generate_questions(wb, regions, patterns) -> list[Question]`
- Raises: `QuestionIdentityError` for ambiguous identity or truncated digest collision

- [ ] **Step 1: Write failing stable-ID and forward-insertion tests**

Add `rule`, `identity_sha256`, and `content_sha256` assertions to the current rule test. Add helpers that select a question by semantic fields rather than list position, then add these tests:

```python
def _by_key(questions, sheet, category, target):
    return next(
        q for q in questions
        if (q.sheet, q.category, q.target) == (sheet, category, target)
    )


def test_sheet_role_id_is_a_stable_golden_value():
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[ir.Sheet(name="入力")],
    )
    question = generate_questions(wb, {"入力": []}, {"入力": []})[0]
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
        generate_questions(base, {"入力": []}, {"入力": []}),
        "入力", "sheet_role", "入力",
    ).id
    expanded_id = _by_key(
        generate_questions(
            expanded,
            {"表紙": [], "入力": []},
            {"表紙": [], "入力": []},
        ),
        "入力", "sheet_role", "入力",
    ).id
    assert expanded_id == base_id
```

Add one test where a sheet is both hidden and protected and assert the two `hidden_reason` questions have rules `hidden_sheet` and `protected_sheet` with different IDs.

In the same RED step, add tests proving NFC-equivalent text and comma spacing have the same digest,
meaningful sheet whitespace is not collapsed, duplicate buttons with the same sheet/macro collapse to
one stable question but create two legacy aliases, and monkeypatched `_short_question_id` results with
different full digests raise `QuestionIdentityError`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
uv run pytest tests/test_questions.py -q
```

Expected: FAIL because current output still uses `q-001` and `Question` has no fingerprint fields.

- [ ] **Step 3: Implement canonical fingerprints and QuestionSet**

Add these public models and exception:

```python
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
```

Implement canonical JSON with `ensure_ascii=False`, `sort_keys=True`, and separators `(",", ":")`. Apply NFC to every value, preserve sheet whitespace, remove only comma-adjacent whitespace from target, and collapse whitespace only in text. Build each candidate with a fixed rule name and append its legacy copy before deduplication:

```python
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

    # Move the existing traversal below this helper unchanged. Replace each existing add call with
    # the rule mapping listed immediately after this block.
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
```

Use the approved rule constants verbatim: `sheet_role`, `hidden_sheet`, `protected_sheet`, `hidden_columns`, `input_region`, `list_validation`, `conditional_format`, `button_macro`, `vba_event`.

Apply them to existing branches exactly as follows; keep the current `sheet/target/category/text` expressions:

```text
every sheet role                         -> sheet_role
sheet.hidden                             -> hidden_sheet
sheet.protected                          -> protected_sheet
sheet.hidden_cols                        -> hidden_columns
formula-free detected region             -> input_region
list validation                          -> list_validation
conditional format                       -> conditional_format
button macro                              -> button_macro
VBA event                                 -> vba_event
```

- [ ] **Step 4: Run Task 1 tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_questions.py tests/test_markdown.py -q
```

Expected: PASS. `tests/test_markdown.py` continues to construct display-only `Question` values via the default fingerprint fields.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/sheetlens/detectors/questions.py tests/test_questions.py
git commit -m "feat: generate stable question IDs"
```

---

### Task 2: Versioned catalog, deterministic persistence, and resolver

**Files:**
- Create: `src/sheetlens/question_ids.py`
- Create: `tests/test_question_ids.py`

**Interfaces:**
- Consumes: `Question`, `QuestionSet`
- Produces: `QuestionIdCatalog`, `AnswerResolution`, `QuestionIdDiagnostic`
- Produces: `build_catalog`, `load_catalog`, `save_catalog`, `resolve_answered_ids`
- Produces: `legacy_snapshot_matches`, `is_legacy_question_id`, `validate_catalog_questions`
- Produces: `record_unresolved_legacy_ids`
- Raises: `QuestionCatalogError`

- [ ] **Step 1: Write failing catalog schema and deterministic-save tests**

Create tests for the exact schema constants, `q-999`/`q-1000` legacy recognition, deterministic JSON, and preservation of alias provenance:

```python
def test_legacy_id_recognizes_minimum_width_not_maximum_width():
    assert is_legacy_question_id("q-999")
    assert is_legacy_question_id("q-1000")
    assert not is_legacy_question_id("q-99")
    assert not is_legacy_question_id("q2-sheet_role-68ae6d6b93515448")


def test_save_catalog_is_deterministic_and_ends_with_newline(tmp_path):
    path = tmp_path / "question-ids.json"
    catalog = _catalog_fixture()
    save_catalog(path, catalog)
    first = path.read_bytes()
    save_catalog(path, catalog)
    assert path.read_bytes() == first
    assert first.endswith(b"\n")
    assert not (tmp_path / ".question-ids.json.tmp").exists()
```

The `_catalog_fixture()` helper must build a real `QuestionSet` through Task 1 APIs, then call `build_catalog`; it must not handcraft unchecked hashes.

Also write RED tests that reject a `QuestionSet` whose stable `Question` has blank rule/fingerprints,
reject a catalog entry whose key/ID/full digest/canonical fields disagree, and reject a catalog whose
`current_ids` differ from a freshly generated `QuestionSet` despite a matching source hash.

- [ ] **Step 2: Run the new unit tests and verify RED**

Run:

```bash
uv run pytest tests/test_question_ids.py -q
```

Expected: collection FAIL because `sheetlens.question_ids` does not exist.

- [ ] **Step 3: Implement strict catalog models and I/O**

Create strict Pydantic models with these exact fields:

```python
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
```

`load_catalog(path: Path, *, expected_source_sha256: str | None = None) -> QuestionIdCatalog | None`
must return `None` only when the file is absent, wrap JSON/Pydantic failures in
`QuestionCatalogError`, and reject source mismatch. `save_catalog(path: Path, catalog:
QuestionIdCatalog) -> None` must sort `current_ids`, question keys, alias keys, and unresolved IDs
before `model_dump_json(indent=2) + "\n"`, write `.question-ids.json.tmp`, then call `replace()`.
Both `build_catalog` and `load_catalog` must recompute canonical identity/content digests and the
`q2-<rule>-<16hex>` ID for every entry; the default blank fingerprint fields remain allowed only for
renderer-only `Question` fixtures and can never enter a catalog.

- [ ] **Step 4: Write failing history/alias merge and answer classification tests**

Cover these exact cases:

```text
current stable ID -> answered_ids contains itself
legacy alias to current ID -> answered_ids contains stable target, legacy_ids contains the source ID
historical ID with one current entry sharing identity -> changed diagnostic with current_id
historical ID with no current identity -> deleted diagnostic
unknown stable or legacy ID -> unresolved diagnostic
previous alias supplied with a different target -> QuestionCatalogError
previous legacy_source_sha256 changed during merge -> QuestionCatalogError
catalog current ID missing from questions -> QuestionCatalogError
legacy alias to historical ID -> alias target is expanded first, then changed/deleted is classified
matching source hash but current catalog differs from fresh QuestionSet -> QuestionCatalogError
```

- [ ] **Step 5: Implement catalog merge, snapshot guard, and resolver**

Use these exact signatures:

- `build_catalog(source_sha256: str, question_set: QuestionSet, *, previous: QuestionIdCatalog | None = None, legacy_aliases: Mapping[str, str] | None = None, legacy_source_sha256: str | None = None, unresolved_legacy_ids: Iterable[str] = ()) -> QuestionIdCatalog`
- `legacy_snapshot_matches(existing: str, expected: str) -> bool`
- `resolve_answered_ids(answered_ids: Iterable[str], catalog: QuestionIdCatalog) -> AnswerResolution`
- `validate_catalog_questions(catalog: QuestionIdCatalog, question_set: QuestionSet) -> None`
- `record_unresolved_legacy_ids(catalog: QuestionIdCatalog, question_ids: Iterable[str]) -> QuestionIdCatalog`

`legacy_snapshot_matches` must normalize only question-line checkbox tokens matching `^- \[[ x]\] (?=\*\*)` in multiline mode, then compare the complete strings. `build_catalog` must preserve all historical question entries, preserve previous aliases and legacy source exactly, and replace only current IDs/source with the new `QuestionSet`. `resolve_answered_ids` must never add changed/deleted/unresolved IDs to `answered_ids`.
For a legacy input, resolve its alias target before classification; if that target is historical, use
the historical entry's identity to return `changed` or `deleted`, never `unresolved` solely because the
alias target is no longer current. `record_unresolved_legacy_ids` returns a validated copy with the
sorted union and never mutates aliases.

- [ ] **Step 6: Run Task 2 tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_question_ids.py tests/test_questions.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add src/sheetlens/question_ids.py tests/test_question_ids.py
git commit -m "feat: persist question ID catalog"
```

---

### Task 3: Legacy bootstrap and re-extract catalog lifecycle

**Files:**
- Modify: `src/sheetlens/pipeline.py:1-134`
- Modify: `src/sheetlens/cli.py:10-27`
- Modify: `tests/test_extract_e2e.py:1-83`

**Interfaces:**
- Consumes: Task 1 `QuestionSet`; Task 2 catalog APIs
- Produces: `Analysis.question_set` and compatibility property `Analysis.questions`
- Produces: `bootstrap_legacy_catalog(proj, wb, analysis) -> QuestionIdCatalog`
- Produces: `_load_or_bootstrap_question_catalog(proj, wb, analysis) -> tuple[QuestionIdCatalog, bool]`
- Produces: `resolve_project_question_ids(proj, wb, analysis, anns, persist) -> ProjectQuestionState`
- Preserves: `extract_workbook(src: Path, out: Path | None = None) -> Path`

- [ ] **Step 1: Write failing extract catalog and YAML-preservation tests**

Extend `test_extract_generates_project` to require `question-ids.json`, schema version 1, generator version 2, and `source_sha256 == raw["sha256"]`.

Add an E2E helper that converts a newly extracted fixture into a legacy project without editing production code:

```python
def _make_legacy_project(proj):
    raw = ir.Workbook.model_validate_json(
        (proj / "structure" / "raw.json").read_text(encoding="utf-8")
    )
    analysis = analyze(raw)
    (proj / "questions.md").write_text(
        render_questions_md(analysis.question_set.legacy_questions, set()),
        encoding="utf-8",
    )
    (proj / "question-ids.json").unlink()
```

Then test: extract workbook A; convert to legacy; write `questions_answered: [q-001]`; save annotation bytes; modify the workbook by inserting a new sheet before the answered sheet; re-run extract; assert annotation bytes unchanged, alias `q-001` still targets the original sheet-role stable ID, `legacy_source_sha256` equals workbook A hash, and `source_sha256` equals workbook B hash.

Before production edits, add RED tests proving:

- changing old `questions.md` text prevents alias creation, and calling Task 2
  `resolve_answered_ids(["q-001"], catalog)` returns an unresolved diagnostic;
- a second re-extract cannot repoint an existing alias even when a new question is inserted first;
- tampering catalog `source_sha256` causes extract failure and leaves `structure/raw.json` bytes unchanged;
- a new workbook with two list validations on the same range but different choices raises
  `QuestionIdentityError` and leaves the entire old `structure/` path-to-bytes mapping unchanged;
- annotation bytes remain unchanged in every success and failure case.

- [ ] **Step 2: Run extract E2E and verify RED**

Run:

```bash
uv run pytest tests/test_extract_e2e.py -q
```

Expected: FAIL because no catalog is generated or preserved.

- [ ] **Step 3: Extend Analysis and add project bootstrap helpers**

Change `Analysis` without breaking existing renderer call sites:

```python
class Analysis(BaseModel):
    patterns: dict[str, list[FormulaPattern]]
    regions: dict[str, list[Region]]
    question_set: QuestionSet

    @property
    def questions(self) -> list[Question]:
        return self.question_set.questions
```

Add the models below. Implement `bootstrap_legacy_catalog(proj, wb, analysis)` as an annotation-free
pure bootstrap over old raw/questions, and `_load_or_bootstrap_question_catalog(proj, wb, analysis)`
as a loader returning `(catalog, bootstrapped_catalog)`. The loader validates source hash and then calls
`validate_catalog_questions(catalog, analysis.question_set)` before returning. Implement the resolution
function with the exact signature shown; it collects annotation IDs only after catalog bootstrap,
records unresolved legacy IDs in the returned catalog, and saves only when `persist` is true.

```python
class ProjectQuestionState(BaseModel):
    catalog: QuestionIdCatalog
    resolution: AnswerResolution
    bootstrapped_catalog: bool = False


def resolve_project_question_ids(
    proj: Path,
    wb: ir.Workbook,
    analysis: Analysis,
    anns: list[SheetAnnotations],
    *,
    persist: bool,
) -> ProjectQuestionState:
    catalog_path = proj / "question-ids.json"
    catalog, bootstrapped_catalog = _load_or_bootstrap_question_catalog(
        proj,
        wb,
        analysis,
    )
    annotation_ids = [qid for ann in anns for qid in ann.questions_answered]
    resolution = resolve_answered_ids(
        annotation_ids,
        catalog,
    )
    catalog = record_unresolved_legacy_ids(
        catalog,
        (
            diagnostic.question_id
            for diagnostic in resolution.diagnostics
            if diagnostic.kind == "unresolved"
            and is_legacy_question_id(diagnostic.question_id)
        ),
    )
    if persist:
        save_catalog(catalog_path, catalog)
    return ProjectQuestionState(
        catalog=catalog,
        resolution=resolution,
        bootstrapped_catalog=bootstrapped_catalog,
    )
```

When the catalog is absent, `bootstrap_legacy_catalog` renders
`analysis.question_set.legacy_questions` with no answered IDs, compares it to existing `questions.md`
through `legacy_snapshot_matches`, and only then uses `question_set.legacy_aliases`. It never imports or
loads annotations. `resolve_project_question_ids` alone sets unresolved IDs from annotations and persists
them only for compile. Check receives the updated in-memory catalog but writes nothing.

- [ ] **Step 4: Integrate catalog loading before destructive extract work**

Refactor `extract_workbook` in this order:

```text
read new workbook and determine project path
analyze the new workbook and build its candidate QuestionSet
if old raw exists: parse old workbook
analyze old workbook
if catalog exists: load it with expected old Workbook.sha256
if catalog is absent: bootstrap aliases from old raw + old questions.md without parsing annotations
validate old catalog current entries against the old QuestionSet
merge old catalog history/aliases into new current catalog
validate the complete merged catalog against the new QuestionSet
only after every read/analyze/validation/merge succeeds: remove/recreate structure
write raw/manifest/views
atomically save question-ids.json
return Path unchanged
```

If an existing catalog is malformed, differs from old raw, or differs from the old generated current
QuestionSet, raise `QuestionCatalogError` before `shutil.rmtree`. If new question generation or catalog
merge fails, likewise preserve all old structure bytes.
Update the extract CLI branch in the same RED/GREEN cycle to catch `QuestionCatalogError` and
`QuestionIdentityError`, print `質問 ID エラー: <message>`, and exit 1 without a traceback.

- [ ] **Step 5: Run Task 3 tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_extract_e2e.py tests/test_questions.py tests/test_question_ids.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/sheetlens/pipeline.py src/sheetlens/cli.py tests/test_extract_e2e.py
git commit -m "feat: migrate legacy question IDs on extract"
```

---

### Task 4: Compile with automatic legacy answer resolution

**Files:**
- Modify: `src/sheetlens/pipeline.py:65-134`
- Modify: `src/sheetlens/cli.py:27-45`
- Modify: `tests/test_compile_e2e.py:1-54`

**Interfaces:**
- Consumes: `resolve_project_question_ids(proj, wb, analysis, anns, persist=True)`
- Produces: `CompileResult(warnings, question_state)`
- Changes: `compile_project(proj) -> CompileResult`

- [ ] **Step 1: Write failing compile migration tests**

Replace hard-coded assumptions that upgraded extract emits `q-001`. Add a legacy-project helper equivalent to Task 3, then assert:

```python
before = annotation_path.read_bytes()
result = runner.invoke(app, ["compile", str(proj)])
assert result.exit_code == 0, result.output
assert annotation_path.read_bytes() == before
assert "旧質問 ID を自動解決: 1 件" in result.output
assert "回答時世代そのものを証明しません" in result.output
assert "**q2-sheet_role-" in (proj / "questions.md").read_text(encoding="utf-8")
assert "- [x] **q2-sheet_role-" in (proj / "questions.md").read_text(encoding="utf-8")
```

Add a snapshot-mismatch test where legacy `q-001` remains unchecked, `質問ID未解決` is printed, and the YAML bytes remain unchanged.

- [ ] **Step 2: Run compile E2E and verify RED**

Run:

```bash
uv run pytest tests/test_compile_e2e.py -q
```

Expected: FAIL because compile still compares annotation strings directly.

- [ ] **Step 3: Implement CompileResult and stable answered-set flow**

Add:

```python
class CompileResult(BaseModel):
    warnings: list[str]
    question_state: ProjectQuestionState
```

In `compile_project`, load annotations, analyze, call
`resolve_project_question_ids(proj, wb, analysis, anns, persist=True)`, and pass
`question_state.resolution.answered_ids` to `_write_views`. Keep orphan/unwoven warnings separate from
question diagnostics in the result.

Update `compile_cmd` to catch `QuestionCatalogError` and `QuestionIdentityError`, print `質問 ID エラー: <message>`, and exit 1. Format each question diagnostic by kind; print the legacy count and `legacy_source_sha256` when legacy aliases were actually used.

- [ ] **Step 4: Run Task 4 tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_compile_e2e.py tests/test_extract_e2e.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/sheetlens/pipeline.py src/sheetlens/cli.py tests/test_compile_e2e.py
git commit -m "feat: resolve legacy question answers"
```

---

### Task 5: Read-only check diagnostics and user-facing documentation

**Files:**
- Modify: `src/sheetlens/cli.py:48-72`
- Modify: `src/sheetlens/renderers/markdown.py:167-212`
- Modify: `README.md:39-75`
- Modify: `tests/test_check_e2e.py:1-50`
- Modify: `tests/test_markdown.py:100-120`

**Interfaces:**
- Consumes: `resolve_project_question_ids(project, wb, analysis, anns, persist=False)`
- Produces: CLI diagnostics `質問ID変更`, `質問ID削除`, `質問ID未解決`
- Preserves: warning-only check exit code 0; catalog corruption/source mismatch exit code 1

- [ ] **Step 1: Write failing check behavior tests**

Add E2E cases for:

```text
catalog absent + valid legacy snapshot -> check resolves in memory and does not create catalog
stable answered ID whose old identity has new content -> 警告（質問ID変更） and current ID
stable answered ID whose question was removed -> 警告（質問ID削除）
unknown ID -> 警告（質問ID未解決）
catalog source mismatch -> exit 1 and 質問 ID エラー
warning-only cases -> exit 0
```

For read-only behavior, capture all project file bytes before `check`, invoke the command, and assert the same path-to-bytes mapping afterward.

- [ ] **Step 2: Run check tests and verify RED**

Run:

```bash
uv run pytest tests/test_check_e2e.py -q
```

Expected: FAIL because check ignores unknown/stale IDs and does not load the catalog.

- [ ] **Step 3: Reuse the common resolver from check without persistence**

Replace direct set membership in `check` with:

```python
state = resolve_project_question_ids(
    project,
    wb,
    analysis,
    anns,
    persist=False,
)
answered = state.resolution.answered_ids
```

Print formatted diagnostics through the same helper used by compile. Catch catalog/question-generation errors and exit 1. Do not call `save_catalog` on any check branch.

- [ ] **Step 4: Update generated and repository documentation**

Add `question-ids.json` to the generated README artifact list and root README output tree. Explain that `q2-*` is stable, old `q-NNN` values remain valid through a preserved alias, annotations are never rewritten, and a legacy alias is based on the pre-upgrade extraction snapshot rather than proof of the human answer timestamp. Update the Markdown example from `q-003` to a representative `q2-input_region-<16hex>` form without claiming a digest not generated by a test fixture.

- [ ] **Step 5: Run Task 5 tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_check_e2e.py tests/test_markdown.py tests/test_compile_e2e.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```bash
git add src/sheetlens/cli.py src/sheetlens/renderers/markdown.py README.md \
  tests/test_check_e2e.py tests/test_markdown.py
git commit -m "feat: report stale question answers"
```

---

### Task 6: Integration verification and project-state completion

**Files:**
- Modify: `docs/project/items/SL-001-stable-question-ids.md`
- Modify: `docs/project/backlog.md` via renderer

**Interfaces:**
- Controller-only: project management files must not be modified by implementation subagents
- Consumes: clean task reviews and final whole-branch review
- Produces: checked acceptance criteria, exact completion evidence, `status: done`, `owner: null`

- [ ] **Step 1: Run focused integration verification**

Run:

```bash
uv run pytest tests/test_questions.py tests/test_question_ids.py \
  tests/test_extract_e2e.py tests/test_compile_e2e.py tests/test_check_e2e.py \
  tests/test_markdown.py -q
```

Expected: all focused tests PASS with no warnings other than explicitly asserted CLI output.

- [ ] **Step 2: Run full repository verification**

Run:

```bash
uv run pytest -q
uv run ruff check .
uv run python scripts/check_project_state.py check
```

Expected: all commands exit 0.

- [ ] **Step 3: Run final whole-branch review and fix all Critical/Important findings**

Use `superpowers:requesting-code-review` with a review package from the merge base through HEAD. The reviewer must look for silent answer reassignment, destructive annotation writes, catalog/source mismatch gaps, and check mutations. Re-run the focused tests after every fix wave.

- [ ] **Step 4: Update SL-001 completion evidence as the parent worker**

In `docs/project/items/SL-001-stable-question-ids.md`:

```text
check every acceptance checkbox
replace the implementation-plan paragraph with a link to this plan
record exact focused/full pytest counts, ruff result, project-state result, and final review verdict
set status: done
set owner: null
```

Then regenerate and validate:

```bash
uv run python scripts/check_project_state.py render
uv run python scripts/check_project_state.py check
uv run pytest -q
uv run ruff check .
```

Expected: all commands exit 0 and `docs/project/backlog.md` shows SL-001 as `done`.

- [ ] **Step 5: Commit project completion**

```bash
git add docs/project/items/SL-001-stable-question-ids.md docs/project/backlog.md
git commit -m "docs: complete SL-001"
```
