# Artifact Presence Implementation Plan

> **For agentic workers:** Use test-driven development. Keep project-state edits parent-owned, and ask independent reviewers to find problems rather than confirm success.

**Goal:** Record chart, image, shape, and pivot presence per worksheet so downstream agents can distinguish absence from unsupported detail extraction.

**Architecture:** Add a backward-compatible sheet-level artifact summary to the IR. A dedicated raw OOXML reader follows workbook, worksheet, and drawing relationships without relying on openpyxl's lossy drawing objects. The workbook reader merges those summaries and diagnostics into the existing IR, and the machine manifest exposes the summaries while retaining unsupported-detail notices in `extraction_gaps`.

**Tech Stack:** Python 3.12+, Pydantic 2, openpyxl 3.1.5, `zipfile`, `xml.etree.ElementTree`, pytest, Ruff.

## Contracts and Boundaries

- `count` is the number of sheet-level placements or references, not the number of distinct parts.
- `ooxml_parts` contains sorted, distinct, package-relative part names. Reusing one image part twice yields `count=2` and one part.
- Supported artifact types are `chart`, `image`, `shape`, and `pivot`.
- Top-level `sp`, `cxnSp`, and `grpSp` drawing objects count as shapes. Children of a group are not counted again.
- Chart and image nodes count as present even when their relationship cannot be resolved; the unresolved part is diagnosed as a gap.
- VML, chartsheets, external targets, alternate content, and unknown graphic frames are not misclassified. Detectable unsupported content is reported as a gap.
- Chart series, image bytes, shape layout/style, pivot definitions/cache contents, VML controls, and chartsheet rendering remain out of scope.
- Existing raw JSON without `artifacts` remains valid and restores an empty list.

## Task 1: Add Failing Contracts

**Files:**
- Modify: `tests/test_ir.py`
- Modify: `tests/test_reader.py`
- Modify: `tests/test_machine.py`

- Add IR round-trip and legacy-payload coverage.
- Add an OOXML fixture with a non-default worksheet target and a drawing containing chart, reused image, shape, and grouped shape placements.
- Add pivot-part coverage and verify pivot caches are not counted.
- Add malformed or dangling relationship coverage that continues extraction and records a deterministic gap.
- Fix manifest shape and unsupported-detail gap contracts.

Run:

```bash
uv run pytest tests/test_ir.py tests/test_reader.py tests/test_machine.py -q
```

Expected before implementation: FAIL for missing artifact models and manifest fields.

## Task 2: Implement OOXML Artifact Extraction

**Files:**
- Add: `src/sheetlens/reader/artifacts.py`
- Modify: `src/sheetlens/model/ir.py`
- Modify: `src/sheetlens/reader/workbook.py`

- Add `SheetArtifact` and `Sheet.artifacts` with fixed vocabulary, positive counts, and distinct deterministic parts.
- Resolve `workbook.xml` sheet relationships instead of assuming `sheetN.xml` ordering.
- Resolve package-absolute and source-relative internal targets safely; diagnose external, escaping, missing, duplicate, and malformed relationships.
- Count referenced worksheet pivot parts and top-level drawing objects. Resolve chart/image parts through drawing relationships.
- Aggregate by sheet and type in fixed order, and append one unsupported-detail gap per recorded type.

## Task 3: Expose Artifact Summaries in the Manifest

**Files:**
- Modify: `src/sheetlens/renderers/machine.py`

- Add `artifacts` to every sheet entry, including an empty list when none are present.
- Preserve artifact diagnostics through the existing `extraction_gaps` field.

Run the focused tests and require PASS.

## Task 4: Review, Verify, and Complete SL-008

- Ask an independent reviewer to search for relationship traversal, path safety, double-counting, compatibility, and silent-loss defects.
- Re-run focused tests after any correction.
- Run the full suite, Ruff, project-state validation, and `git diff --check`.
- Consult Advisor before completion and address actionable findings.
- Check all acceptance criteria, record evidence, set `status: done`, clear `owner`, regenerate backlog, and repeat state validation.
