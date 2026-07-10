# Defined Name Validation Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve static list-validation sources through workbook and sheet-local defined names while preserving unresolved rules and reporting deterministic extraction gaps.

**Architecture:** Keep `ValidationRule` and `read_validations()` backward compatible. Add private structured range/name resolution in `reader/features.py`, use sheet-local then workbook scope, and pass a keyword-only gap sink from `read_workbook()` so expected failures remain isolated to one validation rule.

**Tech Stack:** Python 3.12+, openpyxl 3.1.5, pytest, Ruff, SheetLens dataclass IR.

## Global Constraints

- Evaluate only one static contiguous cell range; do not evaluate arbitrary Excel expressions.
- Resolve defined names case-insensitively within each scope, sheet-local before workbook scope.
- A present but invalid sheet-local name shadows the workbook name and must not fall back.
- Preserve `ValidationRule`, `Workbook.defined_names`, `raw.json`, and the two-argument `read_validations(ws_f, wb_v)` contract.
- Keep unresolved rules with their original `ranges` and `formula1`, use `choices=[]`, and emit one deterministic gap per DataValidation.
- Do not add dependencies or change the IR schema; no data migration is required.
- Only the parent worker may update `docs/project/items/`, `docs/project/backlog.md`, or completion evidence.

---

## File Structure

- `src/sheetlens/reader/features.py`: owns static range parsing, defined-name scope lookup, choice extraction, reason codes, and validation-level gap formatting.
- `src/sheetlens/reader/workbook.py`: owns the workbook-wide `extraction_gaps` list and passes it into validation extraction.
- `tests/test_features.py`: creates real `.xlsx` workbooks and verifies round-trip behavior through `read_workbook()` and direct compatibility calls to `read_validations()`.
- `docs/project/items/SL-005-defined-name-validations.md`: parent-owned status, plan link, acceptance checkboxes, and completion evidence.
- `docs/project/backlog.md`: parent-owned generated project-state view.

### Task 1: Static Range and Workbook Name Resolution

**Files:**
- Modify: `src/sheetlens/reader/features.py:1-44`
- Modify: `tests/test_features.py:1-33`

**Interfaces:**
- Consumes: openpyxl `range_boundaries()`, `range_to_tuple()`, `MAX_COLUMN`, `MAX_ROW`, and `wb_v.defined_names`.
- Produces: `_ListResolution(choices: list[str], reason: str | None)`, `_resolve_list(wb_v, current_sheet: str, formula: str) -> _ListResolution`.

- [ ] **Step 1: Add failing workbook-name, quoted-sheet, direct-current-sheet, and empty-range tests**

Add the imports and helpers below to `tests/test_features.py`:

```python
from openpyxl.workbook.defined_name import DefinedName


def _add_list_validation(ws, target: str, formula: str) -> None:
    dv = DataValidation(type="list", formula1=formula)
    dv.add(target)
    ws.add_data_validation(dv)


def _rules_by_range(workbook, sheet_name: str = "入力"):
    sheet = next(sheet for sheet in workbook.sheets if sheet.name == sheet_name)
    return {rule.ranges[0]: rule for rule in sheet.validations}
```

Add these tests:

```python
def test_resolves_workbook_name_case_insensitively_and_quoted_sheet(make_xlsx):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        master = wb.create_sheet("O'Brien")
        master["A2"] = "通常"
        master["A3"] = "特急"
        wb.defined_names.add(
            DefinedName("Choices", attr_text="'O''Brien'!$A$2:$A$3")
        )
        _add_list_validation(ws, "B2", "=choices")
        _add_list_validation(ws, "C2", "='O''Brien'!$A$2:$A$3")

    workbook = read_workbook(make_xlsx(build))
    rules = _rules_by_range(workbook)
    assert rules["B2"].choices == ["通常", "特急"]
    assert rules["C2"].choices == ["通常", "特急"]
    assert workbook.extraction_gaps == []


def test_resolves_current_sheet_range_and_distinguishes_valid_empty_range(make_xlsx):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        ws["D2"] = "赤"
        ws["D3"] = "青"
        empty = wb.create_sheet("空マスタ")
        wb.defined_names.add(
            DefinedName("EmptyChoices", attr_text="'空マスタ'!$A$1:$A$2")
        )
        _add_list_validation(ws, "B2", "=$D$2:$D$3")
        _add_list_validation(ws, "C2", "=EmptyChoices")

    workbook = read_workbook(make_xlsx(build))
    rules = _rules_by_range(workbook)
    assert rules["B2"].choices == ["赤", "青"]
    assert rules["C2"].choices == []
    assert workbook.extraction_gaps == []
```

- [ ] **Step 2: Run the new tests and confirm the root-cause failures**

Run:

```bash
uv run pytest \
  tests/test_features.py::test_resolves_workbook_name_case_insensitively_and_quoted_sheet \
  tests/test_features.py::test_resolves_current_sheet_range_and_distinguishes_valid_empty_range \
  -q
```

Expected: FAIL because `=choices` and `=EmptyChoices` are treated as cell coordinates, and the apostrophe-escaped sheet title is not normalized.

- [ ] **Step 3: Add structured static-range and workbook-name resolution**

Replace the current `_resolve_list()` implementation in `src/sheetlens/reader/features.py` with these private types and helpers, then update the call in `read_validations()` to use `.choices`:

```python
from dataclasses import dataclass

from openpyxl.utils.cell import range_boundaries, range_to_tuple
from openpyxl.xml.constants import MAX_COLUMN, MAX_ROW

from sheetlens.model import ir


@dataclass(frozen=True)
class _RangeTarget:
    sheet: str
    min_col: int
    min_row: int
    max_col: int
    max_row: int


@dataclass(frozen=True)
class _ListResolution:
    choices: list[str]
    reason: str | None = None


def _formula_source(formula: str) -> str:
    source = formula.strip()
    if source.startswith("="):
        source = source[1:].strip()
    return source


def _parse_static_range(source: str, default_sheet: str | None) -> _RangeTarget | None:
    try:
        if "!" in source:
            sheet, bounds = range_to_tuple(source)
            sheet = sheet.replace("''", "'")
        else:
            if default_sheet is None:
                return None
            sheet = default_sheet
            bounds = range_boundaries(source)
    except (AttributeError, TypeError, ValueError):
        return None

    if any(value is None for value in bounds):
        return None
    min_col, min_row, max_col, max_row = bounds
    if not (
        1 <= min_col <= max_col <= MAX_COLUMN
        and 1 <= min_row <= max_row <= MAX_ROW
    ):
        return None
    return _RangeTarget(sheet, min_col, min_row, max_col, max_row)


def _read_range(wb_v, target: _RangeTarget) -> _ListResolution:
    if target.sheet not in wb_v.sheetnames:
        return _ListResolution([], "sheet_not_found")
    ws = wb_v[target.sheet]
    choices = [
        str(cell.value)
        for row in ws.iter_rows(
            min_col=target.min_col,
            min_row=target.min_row,
            max_col=target.max_col,
            max_row=target.max_row,
        )
        for cell in row
        if cell.value is not None
    ]
    return _ListResolution(choices)


def _find_defined_name(mapping, name: str):
    matches = [
        definition
        for key, definition in mapping.items()
        if key.casefold() == name.casefold()
    ]
    if len(matches) > 1:
        return None, "ambiguous_name"
    return (matches[0], None) if matches else (None, None)


def _resolve_definition(wb_v, definition, *, default_sheet: str | None) -> _ListResolution:
    source = _formula_source(definition.attr_text or "")
    target = _parse_static_range(source, default_sheet)
    if target is None:
        return _ListResolution([], "unsupported_reference")
    return _read_range(wb_v, target)


def _resolve_list(wb_v, current_sheet: str, formula: str) -> _ListResolution:
    source = _formula_source(formula)
    if source.startswith("="):
        return _ListResolution([], "unsupported_reference")

    target = _parse_static_range(source, current_sheet)
    if target is not None:
        return _read_range(wb_v, target)

    definition, reason = _find_defined_name(wb_v.defined_names, source)
    if reason is not None:
        return _ListResolution([], reason)
    if definition is None:
        return _ListResolution([], "name_not_found")
    return _resolve_definition(wb_v, definition, default_sheet=None)
```

In `read_validations()`, use:

```python
choices = _resolve_list(wb_v, ws_f.title, f1).choices
```

- [ ] **Step 4: Run Task 1 tests and the existing feature regression**

Run:

```bash
uv run pytest tests/test_features.py -q
```

Expected: all tests in `tests/test_features.py` PASS; existing inline-list, direct-range, and conditional-format assertions remain green.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/sheetlens/reader/features.py tests/test_features.py
git commit -m "feat: resolve workbook validation names"
```

### Task 2: Sheet-Local Scope and Shadowing

**Files:**
- Modify: `src/sheetlens/reader/features.py`
- Modify: `tests/test_features.py`

**Interfaces:**
- Consumes: Task 1 `_find_defined_name()`, `_resolve_definition()`, and `_ListResolution`.
- Produces: `_resolve_list()` with case-insensitive local-first lookup and qualifier-free local range binding.

- [ ] **Step 1: Add failing local-shadow and workbook-fallback test**

Add:

```python
def test_sheet_local_name_shadows_workbook_name_and_other_sheet_falls_back(make_xlsx):
    def build(wb):
        input_ws = wb.active
        input_ws.title = "入力"
        other_ws = wb.create_sheet("別シート")
        master = wb.create_sheet("共通マスタ")
        master["A2"] = "共通1"
        master["A3"] = "共通2"
        input_ws["D2"] = "ローカル1"
        input_ws["D3"] = "ローカル2"
        wb.defined_names.add(
            DefinedName("Choices", attr_text="'共通マスタ'!$A$2:$A$3")
        )
        input_ws.defined_names.add(
            DefinedName("cHoIcEs", attr_text="$D$2:$D$3")
        )
        _add_list_validation(input_ws, "B2", "=CHOICES")
        _add_list_validation(other_ws, "B2", "=choices")

    workbook = read_workbook(make_xlsx(build))
    input_rules = _rules_by_range(workbook, "入力")
    other_rules = _rules_by_range(workbook, "別シート")
    assert input_rules["B2"].choices == ["ローカル1", "ローカル2"]
    assert other_rules["B2"].choices == ["共通1", "共通2"]
    assert workbook.extraction_gaps == []
```

This test deliberately saves and reloads the workbook through `make_xlsx()` and `read_workbook()`, exercising openpyxl's persisted worksheet-local `defined_names` behavior.

- [ ] **Step 2: Run the local-scope test and verify it fails**

Run:

```bash
uv run pytest \
  tests/test_features.py::test_sheet_local_name_shadows_workbook_name_and_other_sheet_falls_back \
  -q
```

Expected: FAIL because Task 1 searches only `wb_v.defined_names`, so both validations use the workbook definition.

- [ ] **Step 3: Implement local-first lookup without invalid-local fallback**

Replace the name-lookup tail of `_resolve_list()` with:

```python
    if current_sheet not in wb_v.sheetnames:
        return _ListResolution([], "sheet_not_found")

    local_definition, reason = _find_defined_name(
        wb_v[current_sheet].defined_names,
        source,
    )
    if reason is not None:
        return _ListResolution([], reason)
    if local_definition is not None:
        return _resolve_definition(
            wb_v,
            local_definition,
            default_sheet=current_sheet,
        )

    workbook_definition, reason = _find_defined_name(wb_v.defined_names, source)
    if reason is not None:
        return _ListResolution([], reason)
    if workbook_definition is None:
        return _ListResolution([], "name_not_found")
    return _resolve_definition(wb_v, workbook_definition, default_sheet=None)
```

The immediate return for a found local definition is required: if that definition later resolves to `#REF!`, a dynamic function, or an unsupported reference, its error must shadow the workbook definition.

- [ ] **Step 4: Run local-scope and full feature tests**

Run:

```bash
uv run pytest \
  tests/test_features.py::test_sheet_local_name_shadows_workbook_name_and_other_sheet_falls_back \
  -q
uv run pytest tests/test_features.py -q
```

Expected: both commands PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/sheetlens/reader/features.py tests/test_features.py
git commit -m "feat: resolve sheet-local validation names"
```

### Task 3: Unsupported Expressions and Rule-Level Gaps

**Files:**
- Modify: `src/sheetlens/reader/features.py`
- Modify: `src/sheetlens/reader/workbook.py:56-60`
- Modify: `tests/test_features.py`

**Interfaces:**
- Consumes: Task 2 `_ListResolution.reason` reason codes.
- Produces: `read_validations(ws_f, wb_v, *, extraction_gaps: list[str] | None = None) -> list[ir.ValidationRule]`; deterministic validation gap strings in `Workbook.extraction_gaps`.

- [ ] **Step 1: Add failing direct-expression gap tests**

Add `pytest` and `openpyxl` imports:

```python
import openpyxl
import pytest

from sheetlens.reader.features import read_validations
```

Add:

```python
@pytest.mark.parametrize(
    ("formula", "reason"),
    [
        ("=MissingChoices", "name_not_found"),
        ('=INDIRECT("D2:D3")', "unsupported_indirect"),
        ("=OFFSET(D2,0,0,2,1)", "unsupported_offset"),
        (
            "='入力'!$D$2:$D$3,'入力'!$E$2:$E$3",
            "unsupported_reference",
        ),
    ],
)
def test_unresolved_list_source_keeps_rule_and_adds_one_gap(
    make_xlsx, formula, reason
):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        _add_list_validation(ws, "C2", formula)
        dv = DataValidation(type="list", formula1=formula)
        dv.add("D2")
        dv.add("B2")
        ws.add_data_validation(dv)

    workbook = read_workbook(make_xlsx(build))
    sheet = workbook.sheets[0]
    assert len(sheet.validations) == 2
    assert all(rule.formula1 == formula for rule in sheet.validations)
    assert all(rule.choices == [] for rule in sheet.validations)
    assert workbook.extraction_gaps == [
        f"入力: 入力規則 C2 の選択肢を解決できません "
        f"(formula1={formula!r}; reason={reason})",
        f"入力: 入力規則 B2, D2 の選択肢を解決できません "
        f"(formula1={formula!r}; reason={reason})",
    ]
```

- [ ] **Step 2: Add failing defined-expression and invalid-local-shadow tests**

Add:

```python
@pytest.mark.parametrize(
    ("name", "attr_text", "reason"),
    [
        ("DynamicIndirect", 'INDIRECT("入力!$D$2:$D$3")', "unsupported_indirect"),
        ("DynamicOffset", "OFFSET('入力'!$D$2,0,0,2,1)", "unsupported_offset"),
        ("UnqualifiedGlobal", "$D$2:$D$3", "unsupported_reference"),
        ("MissingSheet", "'存在しない'!$A$1:$A$2", "sheet_not_found"),
        ("BrokenRange", "'入力'!#REF!", "invalid_range"),
        (
            "MultipleAreas",
            "'入力'!$D$2:$D$3,'入力'!$E$2:$E$3",
            "unsupported_reference",
        ),
    ],
)
def test_unsupported_workbook_name_definition_adds_gap(
    make_xlsx, name, attr_text, reason
):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        wb.defined_names.add(DefinedName(name, attr_text=attr_text))
        _add_list_validation(ws, "B2", f"={name}")

    workbook = read_workbook(make_xlsx(build))
    rule = workbook.sheets[0].validations[0]
    assert rule.choices == []
    assert rule.formula1 == f"={name}"
    formula = f"={name}"
    assert workbook.extraction_gaps == [
        "入力: 入力規則 B2 の選択肢を解決できません "
        f"(formula1={formula!r}; reason={reason})"
    ]


def test_invalid_local_name_shadows_valid_workbook_name(make_xlsx):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        master = wb.create_sheet("共通マスタ")
        master["A2"] = "共通1"
        master["A3"] = "共通2"
        wb.defined_names.add(
            DefinedName("Choices", attr_text="'共通マスタ'!$A$2:$A$3")
        )
        ws.defined_names.add(
            DefinedName("choices", attr_text="OFFSET($D$2,0,0,2,1)")
        )
        _add_list_validation(ws, "B2", "=CHOICES")

    workbook = read_workbook(make_xlsx(build))
    assert workbook.sheets[0].validations[0].choices == []
    assert workbook.extraction_gaps[0].endswith("reason=unsupported_offset)")
```

Add the ambiguous same-scope test:

```python
def test_case_insensitive_duplicate_names_are_ambiguous(make_xlsx):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        first = wb.create_sheet("第一")
        second = wb.create_sheet("第二")
        first["A1"] = "一"
        second["A1"] = "二"
        wb.defined_names.add(
            DefinedName("Choices", attr_text="'第一'!$A$1")
        )
        wb.defined_names.add(
            DefinedName("choices", attr_text="'第二'!$A$1")
        )
        _add_list_validation(ws, "B2", "=CHOICES")

    workbook = read_workbook(make_xlsx(build))
    assert workbook.sheets[0].validations[0].choices == []
    assert workbook.extraction_gaps == [
        "入力: 入力規則 B2 の選択肢を解決できません "
        "(formula1='=CHOICES'; reason=ambiguous_name)"
    ]
```

- [ ] **Step 3: Add failing API-compatibility and gap-sink test**

Add:

```python
def test_read_validations_preserves_old_return_type_and_appends_to_gap_sink(make_xlsx):
    def build(wb):
        ws = wb.active
        ws.title = "入力"
        _add_list_validation(ws, "B2", "=MissingChoices")

    path = make_xlsx(build)
    wb_f = openpyxl.load_workbook(path, data_only=False)
    wb_v = openpyxl.load_workbook(path, data_only=True)
    empty_sink: list[str] = []
    existing_sink = ["既存gap"]

    rules = read_validations(
        wb_f["入力"],
        wb_v,
        extraction_gaps=empty_sink,
    )
    read_validations(wb_f["入力"], wb_v, extraction_gaps=existing_sink)
    legacy_rules = read_validations(wb_f["入力"], wb_v)

    assert isinstance(rules, list)
    assert isinstance(legacy_rules, list)
    expected = (
        "入力: 入力規則 B2 の選択肢を解決できません "
        "(formula1='=MissingChoices'; reason=name_not_found)"
    )
    assert empty_sink == [expected]
    assert existing_sink == ["既存gap", expected]
```

- [ ] **Step 4: Run Task 3 tests and verify failures**

Run:

```bash
uv run pytest \
  tests/test_features.py::test_unresolved_list_source_keeps_rule_and_adds_one_gap \
  tests/test_features.py::test_unsupported_workbook_name_definition_adds_gap \
  tests/test_features.py::test_invalid_local_name_shadows_valid_workbook_name \
  tests/test_features.py::test_case_insensitive_duplicate_names_are_ambiguous \
  tests/test_features.py::test_read_validations_preserves_old_return_type_and_appends_to_gap_sink \
  -q
```

Expected: FAIL because reason-specific resolution, the keyword-only sink, deterministic formatting, and workbook gap propagation do not exist yet.

- [ ] **Step 5: Add reason classification and deterministic gap formatting**

Add these helpers to `src/sheetlens/reader/features.py`:

```python
def _unsupported_function_reason(source: str) -> str | None:
    upper = source.lstrip().upper()
    if upper.startswith("INDIRECT("):
        return "unsupported_indirect"
    if upper.startswith("OFFSET("):
        return "unsupported_offset"
    return None


def _format_validation_gap(
    sheet: str,
    ranges: list[str],
    formula1: str,
    reason: str,
) -> str:
    sorted_ranges = ", ".join(sorted(ranges))
    return (
        f"{sheet}: 入力規則 {sorted_ranges} の選択肢を解決できません "
        f"(formula1={formula1!r}; reason={reason})"
    )
```

At the start of `_resolve_definition()`, classify dynamic definitions before parsing. After parsing, distinguish malformed qualified references from other unsupported definitions:

```python
    source = _formula_source(definition.attr_text or "")
    function_reason = _unsupported_function_reason(source)
    if function_reason is not None:
        return _ListResolution([], function_reason)
    if "," in source:
        return _ListResolution([], "unsupported_reference")
    target = _parse_static_range(source, default_sheet)
    if target is None:
        reason = "invalid_range" if "!" in source or "#REF!" in source else "unsupported_reference"
        return _ListResolution([], reason)
    return _read_range(wb_v, target)
```

In `_resolve_list()`, classify direct functions after attempting a valid direct range and before name lookup; qualified malformed ranges must be `invalid_range`:

```python
    target = _parse_static_range(source, current_sheet)
    if target is not None:
        return _read_range(wb_v, target)

    function_reason = _unsupported_function_reason(source)
    if function_reason is not None:
        return _ListResolution([], function_reason)
    if "," in source:
        return _ListResolution([], "unsupported_reference")
    if "!" in source or "#REF!" in source:
        return _ListResolution([], "invalid_range")
```

- [ ] **Step 6: Preserve the return type while appending one gap per rule**

Change the signature and list-validation branch in `read_validations()`:

```python
def read_validations(
    ws_f,
    wb_v,
    *,
    extraction_gaps: list[str] | None = None,
) -> list[ir.ValidationRule]:
    gap_sink = [] if extraction_gaps is None else extraction_gaps
    rules: list[ir.ValidationRule] = []
    for dv in ws_f.data_validations.dataValidation:
        f1 = dv.formula1
        ranges = [str(r) for r in dv.sqref.ranges]
        choices: list[str] = []
        if dv.type == "list" and f1:
            if f1.startswith('"'):
                choices = [s.strip() for s in f1.strip('"').split(",")]
            else:
                resolution = _resolve_list(wb_v, ws_f.title, f1)
                choices = resolution.choices
                if resolution.reason is not None:
                    gap_sink.append(
                        _format_validation_gap(
                            ws_f.title,
                            ranges,
                            f1,
                            resolution.reason,
                        )
                    )
        rules.append(
            ir.ValidationRule(
                ranges=ranges,
                type=dv.type or "unknown",
                formula1=f1,
                choices=choices,
            )
        )
    return rules
```

The `is None` expression is required. Using `extraction_gaps or []` would discard a caller-provided empty list and fail the compatibility test.

- [ ] **Step 7: Connect validation gaps to the workbook accumulator**

Change `src/sheetlens/reader/workbook.py:57` to:

```python
            validations = read_validations(
                ws_f,
                wb_v,
                extraction_gaps=gaps,
            )
```

Keep the surrounding sheet-level `try/except` unchanged as the final defense for unexpected exceptions.

- [ ] **Step 8: Run Task 3 and full feature tests**

Run:

```bash
uv run pytest tests/test_features.py -q
```

Expected: all feature tests PASS, including exact gap strings, scope shadowing, legacy call shape, and conditional-format regression.

- [ ] **Step 9: Run lint on changed Python files**

Run:

```bash
uv run ruff check src/sheetlens/reader/features.py src/sheetlens/reader/workbook.py tests/test_features.py
```

Expected: `All checks passed!`

- [ ] **Step 10: Commit Task 3**

```bash
git add src/sheetlens/reader/features.py src/sheetlens/reader/workbook.py tests/test_features.py
git commit -m "fix: report unresolved validation lists"
```

### Task 4: Final Verification, Review, and Project Completion

**Files:**
- Modify by parent only: `docs/project/items/SL-005-defined-name-validations.md`
- Regenerate by parent only: `docs/project/backlog.md`

**Interfaces:**
- Consumes: all Task 1-3 commits and their passing focused tests.
- Produces: independently reviewed implementation, complete validation evidence, and SL-005 `done` state.

- [ ] **Step 1: Run the focused test suite**

Run:

```bash
uv run pytest tests/test_features.py -q
```

Expected: all tests PASS with no warnings or errors.

- [ ] **Step 2: Run the whole repository test suite**

Run:

```bash
uv run pytest -q
```

Expected: all tests PASS.

- [ ] **Step 3: Run repository-wide lint**

Run:

```bash
uv run ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 4: Request an independent problem-finding review**

Use `superpowers:requesting-code-review` or the repository's reviewer subagent. Ask it to inspect the complete diff for incorrect scope precedence, case-insensitive collisions, malformed-range classification, dynamic functions hidden in defined names, lost validations, duplicate/non-deterministic gaps, and compatibility regressions. Do not ask only for confirmation.

Expected: every Critical and Important finding is either fixed and retested or rejected with code/test evidence. Re-run Steps 1-3 after any fix.

- [ ] **Step 5: Update SL-005 completion evidence as the parent worker**

In `docs/project/items/SL-005-defined-name-validations.md`:

- Change all three acceptance checkboxes from `[ ]` to `[x]`.
- Change `status: in_progress` to `status: done`.
- Change `owner: codex` to `owner: null`.
- Keep the design link and add this plan link:

```markdown
[`2026-07-11-defined-name-validations.md`](../../superpowers/plans/2026-07-11-defined-name-validations.md)
```

- Replace `完了証拠` with the exact observed focused/full/lint/project-state counts and the final review result; do not copy expected counts from this plan.

- [ ] **Step 6: Regenerate and validate project state**

Run:

```bash
uv run python scripts/check_project_state.py render
uv run python scripts/check_project_state.py check
git diff --check
```

Expected: render reports `docs/project/backlog.md`, project-state check exits 0 with no output, and `git diff --check` exits 0 with no output.

- [ ] **Step 7: Re-run focused tests after the `done` transition**

Run:

```bash
uv run pytest tests/test_features.py -q
```

Expected: all focused tests PASS.

- [ ] **Step 8: Commit project completion**

```bash
git add docs/project/items/SL-005-defined-name-validations.md docs/project/backlog.md
git commit -m "docs: complete SL-005"
```

- [ ] **Step 9: Verify the final commit and clean worktree**

Run:

```bash
git status --short --branch
git log -4 --oneline
```

Expected: no modified or untracked files; the latest commit is `docs: complete SL-005` after the three implementation commits.
