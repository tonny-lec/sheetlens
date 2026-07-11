# Conditional Format IR Completion Implementation Plan

> **For agentic workers:** Implement task-by-task with test-driven development. Keep project-state edits parent-owned, and ask independent reviewers to find problems rather than confirm success.

**Goal:** Preserve all formulas, dxf data, and the three primary conditional-format visualization payloads through extraction, JSON, Markdown, and dependency analysis while automatically accepting legacy singular-formula input.

**Architecture:** Extend the Pydantic IR with canonical `formulas` and typed visualization payloads, plus a JSON-safe recursive OOXML node for dxf. Normalize each openpyxl rule independently in `reader/features.py`, append deterministic gaps for unsupported or malformed rules, and keep the workbook-level catch only as a final defense. Update only the two downstream consumers that currently assume one formula.

**Tech Stack:** Python 3.12+, Pydantic 2, openpyxl 3.1.5, pytest, Ruff.

## Global Constraints

- Fully support only `cellIs`, `expression`, `colorScale`, `dataBar`, and `iconSet`.
- Preserve common fields for unsupported or malformed rules and emit at most one gap per rule.
- Canonical output uses `formulas`; legacy `formula` constructor, JSON input, read access, and assignment remain compatible without manual migration.
- Preserve RGB, theme, indexed, and auto colors; do not expose openpyxl objects in the IR.
- Do not implement visual rendering or specialized payloads for other rule types.
- Do not let one rule-level extraction error remove later rules on the same sheet.
- Only the parent worker may update `docs/project/items/`, `docs/project/backlog.md`, or completion evidence.

---

## File Structure

- `src/sheetlens/model/ir.py`: conditional-format schema, recursive dxf node, and legacy formula migration.
- `src/sheetlens/reader/features.py`: openpyxl normalization, payload validation, rule-level isolation, and gap formatting.
- `src/sheetlens/reader/workbook.py`: passes the workbook gap sink into conditional-format extraction.
- `src/sheetlens/renderers/machine.py`: reads every conditional-format formula for dependencies.
- `src/sheetlens/renderers/markdown.py`: summarizes every formula and supported visualization payload.
- `tests/test_ir.py`: migration and JSON contracts.
- `tests/test_features.py`: real workbook round trips, malformed/unsupported gaps, and isolation.
- `tests/test_machine.py`: later-formula dependency coverage.
- `tests/test_markdown.py`: formula and payload summaries.
- `tests/test_extract_e2e.py`: `structure/raw.json` propagation.

### Task 0: Mark SL-006 In Progress

**Files:**
- Modify: `docs/project/items/SL-006-conditional-format-ir.md`
- Regenerate: `docs/project/backlog.md`

- [ ] **Step 1: Update the canonical issue before production changes**

Set `status: in_progress`, set `owner: codex`, and replace the implementation-plan placeholder with a link to this plan. Do not mark acceptance checkboxes yet.

- [ ] **Step 2: Regenerate and validate project state**

```bash
uv run python scripts/check_project_state.py render
uv run python scripts/check_project_state.py check
```

Expected: both commands PASS and the backlog shows SL-006 as the sole in-progress issue.

- [ ] **Step 3: Commit the state transition**

```bash
git add docs/project/items/SL-006-conditional-format-ir.md docs/project/backlog.md
git commit -m "docs: start SL-006"
```

### Task 1: Add the Backward-Compatible IR Schema

**Files:**
- Modify: `src/sheetlens/model/ir.py:1-29`
- Modify: `tests/test_ir.py:1-30`

**Interfaces:**
- Produces `ConditionalValue`, `ConditionalColor`, `ConditionalColorScale`, `ConditionalDataBar`, `ConditionalIconSet`, and recursive `OoxmlNode` models.
- Changes `ConditionalFormat.formula` storage to canonical `formulas: list[str]` while retaining a compatibility property and setter.

- [ ] **Step 1: Add failing migration and payload round-trip tests**

Cover all of the following in `tests/test_ir.py`:

- legacy constructor and `model_validate()` input with `formula="0"` become `formulas=["0"]`;
- `formula=None` becomes an empty list;
- simultaneous `formula` and `formulas` input prefers `formulas`;
- `cf.formula` returns the first formula and assignment replaces the first formula without removing later formulas;
- assigning `None` clears formulas;
- `model_dump()` emits `formulas` and not `formula`;
- visualization models round-trip RGB, theme, indexed, and auto (`value=True`) colors;
- a nested dxf `OoxmlNode` round-trips through workbook JSON.

- [ ] **Step 2: Run the focused tests and confirm they fail for the missing schema**

```bash
uv run pytest tests/test_ir.py -q
```

Expected: FAIL because the new models and `formulas` contract do not exist.

- [ ] **Step 3: Implement the new Pydantic models and legacy migration**

Use `Field(default_factory=list)` for all list fields and a model-level before validator for legacy input. Remove the legacy key before normal validation so Pydantic does not silently ignore it. Implement the `formula` property and setter against `formulas`, preserving elements after index zero when replacing a non-empty list.

- [ ] **Step 4: Run IR tests and the existing direct model consumers**

```bash
uv run pytest tests/test_ir.py tests/test_machine.py tests/test_markdown.py -q
```

Expected: PASS. Existing fixtures that construct with `formula=` remain valid.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/sheetlens/model/ir.py tests/test_ir.py
git commit -m "feat: add conditional format payload models"
```

### Task 2: Preserve Multiple Formulas and dxf per Rule

**Files:**
- Modify: `src/sheetlens/reader/features.py:217-232`
- Modify: `src/sheetlens/reader/workbook.py:61-69`
- Modify: `tests/test_features.py:1-49`

**Interfaces:**
- Adds private normalizers for primitive values, openpyxl colors, and XML elements.
- Changes `read_conditional_formats(ws_f, *, extraction_gaps=None)` to collect every formula and normalized dxf.
- Establishes rule-level isolation before introducing any new extraction failure point.

- [ ] **Step 1: Add failing real-workbook tests for formulas and dxf**

Create and save/reload rules covering:

- `CellIsRule(operator="between", formula=["1", "10"])`;
- an `expression` rule containing multiple formulas;
- a differential style with representative font, fill, and border content;
- multiple rules and a multi-range `sqref`.

Also inject a dxf normalization failure and an unexpected rule failure. Assert `invalid_dxf` or `extraction_error`
is appended once, later rules remain present, and a caller-provided gap list is not replaced.

Assert formula order, range strings, operator, stop-if-true, and recursive dxf content after `read_workbook()`.

- [ ] **Step 2: Confirm root-cause failures**

```bash
uv run pytest tests/test_features.py -q
```

Expected: FAIL because only the first formula is stored and dxf is discarded.

- [ ] **Step 3: Add common-field and dxf normalization**

Implement private helpers that:

- copy all `rule.formula` entries as strings in original order;
- serialize `rule.dxf.to_tree()` into `OoxmlNode` recursively;
- preserve openpyxl-generated tag/attribute names and stringify attributes/text;
- catch dxf normalization errors locally, record `invalid_dxf`, and continue building the rule;
- wrap the remaining rule extraction in a per-rule boundary that records `extraction_error` and continues iteration;
- retain the existing one-argument API by making the gap sink keyword-only and optional.

Pass the workbook gap list into `read_conditional_formats()` in this task. Select at most one final reason per rule,
and keep the existing sheet-level catch only as a final defense. This keeps the intermediate commit no less isolated
than the code it replaces.

Do not add visualization extraction in this task.

- [ ] **Step 4: Run the focused feature regression**

```bash
uv run pytest tests/test_features.py -q
```

Expected: PASS for formula and dxf tests; existing validation tests remain green.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/sheetlens/reader/features.py src/sheetlens/reader/workbook.py tests/test_features.py
git commit -m "feat: preserve conditional format formulas and styles"
```

### Task 3: Extract Visualization Payloads and Isolate Rule Failures

**Files:**
- Modify: `src/sheetlens/reader/features.py`
- Modify: `tests/test_features.py`

**Interfaces:**
- Produces typed payloads for color scale, data bar, and icon set rules.
- Emits one deterministic conditional-format gap with a fixed reason code per unsupported or malformed rule.
- Aggregates rule gaps into `Workbook.extraction_gaps`.

- [ ] **Step 1: Add failing visualization round-trip tests**

Use openpyxl rules saved and reloaded from `.xlsx` to verify:

- color scale conditions and matching RGB/theme/indexed colors;
- data bar start/end conditions, auto color, show-value, min-length, and max-length;
- icon-set style, conditions, show-value, percent, and reverse;
- the three payloads survive `read_workbook()` without gaps.

- [ ] **Step 2: Add failing malformed, unsupported, and isolation tests**

Cover:

- missing and invalid payload reason codes for each visualization type;
- a known unsupported type such as `top10` retaining common fields with `unsupported_type`;
- multiple problems on one rule producing only one gap;
- direct `read_conditional_formats(ws_f)` still returning a list;
- rule gaps reaching `Workbook.extraction_gaps`.

- [ ] **Step 3: Run focused tests and confirm failures**

```bash
uv run pytest tests/test_features.py -q
```

Expected: FAIL because visualization payloads, rule-level validation, and gap aggregation are absent.

- [ ] **Step 4: Implement typed normalization and deterministic validation**

Normalize `cfvo` as `(type, value, gte)` and colors as `(type, value, tint)`. Validate only the invariants in the approved design. Keep dxf extraction in its existing local catch, then continue into visualization extraction even when dxf failed. Accumulate the dxf and payload result before selecting one final reason, so `invalid_dxf` does not discard a valid visualization payload.

Reason selection must be deterministic: payload-specific missing/invalid errors take precedence during known-type extraction; dxf-only failure uses `invalid_dxf`; an otherwise unclassified exception uses `extraction_error`; unsupported type uses `unsupported_type`.

Retain the Task 2 rule-level boundary and the sheet-level catch as the final defense for failures outside it.

- [ ] **Step 5: Run all reader/model tests**

```bash
uv run pytest tests/test_ir.py tests/test_features.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/sheetlens/reader/features.py tests/test_features.py
git commit -m "feat: extract conditional format visual rules"
```

### Task 4: Use Every Formula in Dependency Analysis

**Files:**
- Modify: `src/sheetlens/renderers/machine.py:29-38`
- Modify: `tests/test_machine.py:57-83`

- [ ] **Step 1: Add a failing later-formula dependency test**

Create a conditional format whose first formula has no sheet reference and whose second formula references another sheet. Also cover `formulas=[]`.

- [ ] **Step 2: Confirm the dependency is missing**

```bash
uv run pytest tests/test_machine.py -q
```

Expected: FAIL because only `cf.formula` is inspected.

- [ ] **Step 3: Flatten every conditional-format formula into dependency input**

Iterate `cf.formulas` directly. Do not use the compatibility property in new internal code.

- [ ] **Step 4: Run machine and IR regression tests**

```bash
uv run pytest tests/test_machine.py tests/test_ir.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/sheetlens/renderers/machine.py tests/test_machine.py
git commit -m "fix: include all conditional format dependencies"
```

### Task 5: Summarize Formulas and Visualization Payloads in Markdown

**Files:**
- Modify: `src/sheetlens/renderers/markdown.py:140-149`
- Modify: `tests/test_markdown.py:1-112`

- [ ] **Step 1: Add failing Markdown tests**

Verify that Markdown:

- displays every formula in original order;
- keeps the existing single-formula `lessThan 0` output useful;
- summarizes color scale conditions/colors, data bar settings, and icon-set settings;
- safely displays a rule with no formulas;
- continues annotation weaving for multi-range conditional formats.

- [ ] **Step 2: Run tests and confirm missing summaries**

```bash
uv run pytest tests/test_markdown.py -q
```

Expected: FAIL for multiple formulas and visual payloads.

- [ ] **Step 3: Add small private formatting helpers**

Format the typed IR only; do not inspect openpyxl objects. Keep summaries deterministic and textual. Avoid visual emulation and avoid changing unrelated Markdown sections.

- [ ] **Step 4: Run Markdown and annotation regressions**

```bash
uv run pytest tests/test_markdown.py tests/test_questions.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```bash
git add src/sheetlens/renderers/markdown.py tests/test_markdown.py
git commit -m "feat: document conditional format payloads"
```

### Task 6: Prove raw.json End-to-End Propagation

**Files:**
- Modify: `tests/test_extract_e2e.py:1-99`

- [ ] **Step 1: Extend the extract fixture with representative conditional formats**

Add at least one multiple-formula rule and one visualization rule to the generated workbook. Assert `structure/raw.json` contains canonical `formulas`, the expected typed payload, and dxf while omitting the legacy `formula` key.

- [ ] **Step 2: Run the E2E test**

```bash
uv run pytest tests/test_extract_e2e.py::test_extract_generates_project -q
```

Expected: PASS after Tasks 1–5; if it fails, fix the earliest serialization or pipeline boundary rather than special-casing E2E output.

- [ ] **Step 3: Run all targeted SL-006 tests**

```bash
uv run pytest tests/test_ir.py tests/test_features.py tests/test_machine.py tests/test_markdown.py tests/test_extract_e2e.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit Task 6**

```bash
git add tests/test_extract_e2e.py
git commit -m "test: verify conditional format raw output"
```

### Task 7: Independent Review, Full Verification, and Project Completion

**Files:**
- Modify: `docs/project/items/SL-006-conditional-format-ir.md`
- Regenerate: `docs/project/backlog.md`

- [ ] **Step 1: Run an independent problem-finding review**

Ask the reviewer to inspect compatibility, Pydantic serialization, openpyxl round-trip fidelity, rule-level exception isolation, deterministic gaps, renderer output, and whether the patch exceeds the five supported rule types. Spot-check at least one important reviewer claim directly before changing code or documentation.

- [ ] **Step 2: Apply justified review fixes and rerun affected focused tests**

Do not expand into unsupported rule payloads or visual rendering. Commit each coherent review fix separately.

- [ ] **Step 3: Consult Advisor before completion**

Ask specifically for missed failure modes, compatibility regressions, and unnecessary scope. Resolve actionable findings or record why they do not apply.

- [ ] **Step 4: Update parent-owned project state to the candidate done state**

In `docs/project/items/SL-006-conditional-format-ir.md`:

- link this implementation plan;
- mark each acceptance checkbox only when supported by test evidence;
- set `status: done` and `owner: null`;
- add exact focused verification results and independent-review disposition.

Regenerate `docs/project/backlog.md`. Do not commit this candidate state until the post-update completion gate passes.

- [ ] **Step 5: Run the post-update completion gate**

```bash
uv run python scripts/check_project_state.py render
uv run python scripts/check_project_state.py check
uv run pytest -q
uv run ruff check .
git diff --check
```

Expected: all commands PASS after the candidate `done` update. Record the actual test count; do not claim success from expected output. If any command fails, return the issue to `in_progress`, fix the cause, and repeat this step.

- [ ] **Step 6: Commit the verified completion evidence**

```bash
git add docs/project/items/SL-006-conditional-format-ir.md docs/project/backlog.md
git commit -m "docs: complete SL-006"
```
