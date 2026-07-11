# Cell Display Semantics Implementation Plan

> **For agentic workers:** Use test-driven development. Keep project-state edits parent-owned, and ask independent reviewers to find problems rather than confirm success.

**Goal:** Preserve each extracted cell's value type, exact Excel number format, and a minimal display-semantic category through raw JSON, then expose those semantics in Markdown without implementing a complete Excel display engine.

**Architecture:** Extend `Cell` with optional, backward-compatible metadata. Classify the original openpyxl value before coercion, using the cached-value workbook for formula result types and the formula workbook for number formats. Keep raw values unchanged; add a compact Markdown section for cells whose display semantics matter.

**Tech Stack:** Python 3.12+, Pydantic 2, openpyxl 3.1.5, pytest, Ruff.

## Constraints

- Preserve `number_format` exactly, including `General`.
- Use normalized semantic vocabulary rather than openpyxl data-type codes.
- Support percentage, currency, date, time, datetime, duration, leading-zero, and Excel error semantics.
- Treat numeric fixed-width formats and text values such as `00123` as leading-zero semantics.
- Do not implement Excel's complete locale-aware number-format rendering.
- Do not include style-only empty cells; the existing reader continues to skip cells whose formula-side value is `None`.
- Only the parent worker updates `docs/project/items/` and `docs/project/backlog.md`.

## Task 1: Add Failing Contracts

**Files:**
- Modify: `tests/test_ir.py`
- Modify: `tests/test_reader.py`
- Modify: `tests/test_markdown.py`

- Add JSON round-trip coverage for the new optional cell metadata and legacy input without it.
- Add real `.xlsx` extraction coverage for percentage, currency, date, time, datetime, duration, numeric and text leading-zero values, and Excel errors.
- Cover a formula with no cached value and ensure formula text is preserved without inventing a result type.
- Add adversarial format coverage so quoted or escaped percent signs do not become percentage semantics.
- Add deterministic Markdown coverage for semantic category, value type, and exact number format while preserving the existing grid.

Run:

```bash
uv run pytest tests/test_ir.py tests/test_reader.py tests/test_markdown.py -q
```

Expected before implementation: FAIL for missing fields and semantic output.

## Task 2: Implement Cell Metadata and Classification

**Files:**
- Modify: `src/sheetlens/model/ir.py`
- Modify: `src/sheetlens/reader/workbook.py`

- Add optional `value_type`, `number_format`, and `display_semantics` fields with fixed vocabularies.
- Classify the uncoerced value, with bool-before-number ordering and openpyxl error codes taking precedence.
- Use `openpyxl.styles.numbers.is_datetime()` and `is_timedelta_format()` for date/time semantics.
- Add bounded helpers for active percent tokens, currency markers, and fixed-width leading-zero formats.
- Build formula and non-formula cells through one helper; formula result metadata comes from the cached-value cell.

Run the Task 1 tests and require PASS.

## Task 3: Expose Semantics in Markdown

**Files:**
- Modify: `src/sheetlens/renderers/markdown.py`

- Keep the raw grid value unchanged.
- Add `## セル表示情報` only when at least one cell has `display_semantics`.
- Emit deterministic lines containing the cell reference, semantic category, normalized value type, and exact number format.
- Escape inline-code delimiters in number formats safely.

Run the focused tests, then all renderer and extraction tests.

## Task 4: Verify and Complete SL-007

- Run focused tests, the full suite, Ruff, and project-state validation.
- Ask an independent reviewer to search for classification, formula-cache, compatibility, and Markdown escaping defects.
- Consult Advisor before completion and fix actionable findings.
- Update acceptance checkboxes and completion evidence, set `status: done`, clear `owner`, regenerate the backlog, and repeat project-state plus focused verification.
