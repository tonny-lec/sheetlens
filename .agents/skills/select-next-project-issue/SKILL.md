---
name: select-next-project-issue
description: Use when starting or resuming SheetLens repository work and one project issue must be selected under the solo sequential workflow.
---

# Select Next Project Issue

## Overview

Return one issue to continue or start. Read project state without changing it.

## Workflow

1. Run `uv run python scripts/check_project_state.py check` from the repository root. Stop on a nonzero exit and report the validation output.
2. Read the validated `docs/project/backlog.md` and count rows whose status is `in_progress`.
3. If exactly one issue is active, read its linked file under `docs/project/items/` and return it with `判定: 継続`. Do not run a new selection.
4. If multiple issues are active, return no issue. Report every active ID and state that solo sequential work requires resolving the active set first.
5. If none are active, run `uv run python scripts/check_project_state.py next`. Accept candidates only after exit 0 and only from lines matching `^P[0-3] SL-[0-9]{3} `.
6. Select the first candidate line. If none exist, report `着手可能な課題なし`.
7. Resolve exactly one `docs/project/items/SL-NNN-*.md`, read it, and return the contract below. Stop if resolution is not unique.

## Output Contract

Return fields in this order:

```text
判定: 継続 | 新規着手
課題: SL-NNN 課題名
優先度: P0 | P1 | P2 | P3
状態: in_progress | ready
マイルストーン: M1 | M2 | M3 | M4
正本: docs/project/items/SL-NNN-*.md
理由: 現在進行中の課題、または next の最上位候補
```

## Quick Reference

| State | Result |
|---|---|
| One `in_progress` | Return it as `継続` |
| Multiple `in_progress` | Return no selection; list active IDs |
| No `in_progress`, candidate exists | Return first `next` candidate as `新規着手` |
| No candidate | Report `着手可能な課題なし` |
| Validation or CLI error | Stop and report the error |

## Example

Given `SL-020` in progress and a higher-priority `SL-010` ready, return `SL-020` as `継続` because solo sequential work finishes the active issue before selecting another.

## Common Mistakes

- Do not treat validation output as candidate output; check the exit status first.
- Do not select a ready issue while one issue is in progress.
- Do not update project-management files; this skill only selects and reports.
