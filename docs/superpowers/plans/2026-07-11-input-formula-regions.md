# Input and Formula Region Separation Implementation Plan

**Goal:** Preserve input-source questions for manual portions of a detected region without asking about formula cells or merging blank-column-separated content.

**Architecture:** Keep `Region` backward compatible. Refine region detection into non-empty row bands and contiguous occupied-column bands. Add an input-range projection that returns the original range when no formulas exist, groups pure manual columns into full-height ranges, and emits contiguous manual row runs for columns that mix literals and formulas. Table headers inform column classification but are not treated as manual data in mixed columns.

**Tech Stack:** Python 3.12+, openpyxl coordinate utilities, Pydantic, pytest, Ruff.

## Constraints

- Preserve the existing `Region(range, kind)` schema and deterministic ordering.
- Treat `formula is not None` as authoritative even when a cached value exists.
- Do not infer empty columns as manual input when a region contains formulas.
- Ignore formulas outside the current region.
- Preserve the original range exactly when the region has no formulas.
- Expect changed stable question IDs only where the corrected target range changes.
- Preserve unrelated SL-008 worktree changes.

## Tasks

- [x] Add failing tests for blank-column region separation, detached headers, manual/formula/manual columns, formula-only regions, sparse formula-free regions, mixed columns, and out-of-region formulas.
- [x] Refine `detect_regions()` to split row bands by fully empty column bands and trim each result to its occupied rows.
- [x] Add deterministic input-range projection and generate one `input_source` question per projected range.
- [x] Run focused tests, the full suite, Ruff, project-state validation, and diff checks.
- [x] Review correctness and regression risks, then record completion evidence in SL-011.
