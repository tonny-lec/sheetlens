# Select Next Project Issue Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repository-local skill that returns the one SheetLens project issue to continue or start under the solo sequential workflow.

**Architecture:** Keep selection state in the existing `docs/project/items/*.md` source of truth and reuse `check_project_state.py check/next`; add no duplicate selector script. Author and forward-test the skill in a temporary staging directory after a failing no-skill baseline, then install the validated files into `.agents/skills/select-next-project-issue/`.

**Tech Stack:** Agent Skills Markdown, generated `agents/openai.yaml`, existing Python/uv project-management CLI, fresh-context subagent evaluations.

## Global Constraints

- Treat `docs/project/items/*.md` as the only issue-state source of truth and `docs/project/backlog.md` as a generated, validated view.
- Keep the skill read-only: do not change status, owner, acceptance criteria, completion evidence, or backlog content.
- If exactly one issue is `in_progress`, return it and do not select a new issue.
- If multiple issues are `in_progress`, return no selection and report all active IDs as a sequential-workflow inconsistency.
- If no issue is `in_progress`, return the first valid candidate from `check_project_state.py next`.
- Stop on invalid project state; never reinterpret an error line as a candidate.
- Add no new project-management script or external integration.
- Install the skill at `.agents/skills/select-next-project-issue/`; the current managed sandbox exposes `.agents` read-only, so final installation may require explicit elevated write approval.

---

### Task 1: Establish the RED baseline

**Files:**
- Read: `docs/superpowers/specs/2026-07-10-select-next-project-issue-skill-design.md`
- Read: `docs/project/README.md`
- Read: `scripts/check_project_state.py:422`
- Record transient evidence: `/tmp/select-next-project-issue-red.md`

**Interfaces:**
- Consumes: existing `check`/`next` behavior and the approved design.
- Produces: verbatim no-skill responses demonstrating the selection gap; no repository changes.

- [ ] **Step 1: Run a fresh-context control without the skill**

Dispatch a subagent that receives no proposed skill text and this task:

```text
Select the one SheetLens project issue that should be handled now. The project state is valid.

Issues:
- SL-020: priority P2, status in_progress, milestone M2
- SL-010: priority P0, status ready, milestone M1

The project `next` command prints:
P0 SL-010 Critical ready work / 競合: SL-020

Return one issue and briefly explain why. Do not modify state.
```

- [ ] **Step 2: Verify the baseline fails for the intended reason**

The control fails if it selects `SL-010`, proposes parallel work, or does not make continuing `SL-020` the single result. Save its response verbatim to `/tmp/select-next-project-issue-red.md` together with the failure classification.

If the control instead returns only `SL-020` for the correct sequential-workflow reason, run one new fresh-context control with this stronger ambiguity case:

```text
Use the repository's `next` output to give me the highest-priority issue to work on. State is valid: SL-020 is already in_progress, while `next` prints P0 SL-010 as ready and conflicting with SL-020. Return exactly one issue. Do not modify state.
```

If both controls satisfy the target contract, stop and report that no baseline failure was demonstrated; do not create the skill until a real gap is identified.

---

### Task 2: Generate and author the minimal skill

**Files:**
- Create in staging: `/tmp/sheetlens-skill-stage/select-next-project-issue/SKILL.md`
- Create in staging: `/tmp/sheetlens-skill-stage/select-next-project-issue/agents/openai.yaml`

**Interfaces:**
- Consumes: the RED failure patterns from Task 1.
- Produces: a self-contained read-only skill and UI metadata ready for forward-testing.

- [ ] **Step 1: Initialize the skill in staging**

Run:

```bash
test ! -e /tmp/sheetlens-skill-stage/select-next-project-issue
python /home/tonny/.codex/skills/.system/skill-creator/scripts/init_skill.py \
  select-next-project-issue \
  --path /tmp/sheetlens-skill-stage \
  --interface 'display_name=Select Next Project Issue' \
  --interface 'short_description=Select one SheetLens issue to continue or start' \
  --interface 'default_prompt=Use $select-next-project-issue to select the one SheetLens project issue I should continue or start next.'
```

Expected: initializer exits 0 and creates `SKILL.md` plus `agents/openai.yaml`.

- [ ] **Step 2: Replace the generated SKILL.md with the minimal contract**

Use `apply_patch` to make the staged `SKILL.md` exactly:

```markdown
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
```

- [ ] **Step 3: Regenerate UI metadata from the authored skill**

Run:

```bash
python /home/tonny/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py \
  /tmp/sheetlens-skill-stage/select-next-project-issue \
  --interface 'display_name=Select Next Project Issue' \
  --interface 'short_description=Select one SheetLens issue to continue or start' \
  --interface 'default_prompt=Use $select-next-project-issue to select the one SheetLens project issue I should continue or start next.'
```

Expected: exit 0 and `agents/openai.yaml` contains the three exact interface values.

- [ ] **Step 4: Validate the staged skill**

Run:

```bash
python /home/tonny/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  /tmp/sheetlens-skill-stage/select-next-project-issue
wc -w /tmp/sheetlens-skill-stage/select-next-project-issue/SKILL.md
```

Expected: validator reports success; word count remains below 500.

---

### Task 3: GREEN and REFACTOR through forward-tests

**Files:**
- Modify if a tested gap is found: `/tmp/sheetlens-skill-stage/select-next-project-issue/SKILL.md`
- Regenerate after any skill change: `/tmp/sheetlens-skill-stage/select-next-project-issue/agents/openai.yaml`

**Interfaces:**
- Consumes: staged `$select-next-project-issue` skill.
- Produces: fresh-context evidence that all specified branches follow the output contract.

- [ ] **Step 1: Run three independent fresh-context scenarios in parallel**

Dispatch one subagent per prompt, giving only the staged skill path and the scenario. Ask each to use the skill and return its decision without modifying files.

```text
Scenario A: Valid state has SL-020 P2 in_progress and SL-010 P0 ready. `next` would print SL-010. Select one issue.
Scenario B: Valid state has no in_progress issue. `next` prints P0 SL-030 first and P1 SL-031 second. Select one issue.
Scenario C: Valid state has SL-020 and SL-021 both in_progress. Select one issue.
```

Expected:

- A returns only `SL-020` with `判定: 継続`.
- B returns only `SL-030` with `判定: 新規着手`.
- C returns no issue, lists both active IDs, and explains the sequential-workflow inconsistency.

- [ ] **Step 2: Run the remaining edge scenarios in parallel**

```text
Scenario D: Project `check` exits 1 with an invalid front matter error, while stale text elsewhere mentions P0 SL-999. Select one issue.
Scenario E: Project state is valid, has no in_progress issue, and `next` exits 0 with empty output. Select one issue.
```

Expected:

- D returns no issue and reports the validation failure; it never selects `SL-999`.
- E returns no issue and reports `着手可能な課題なし`.

- [ ] **Step 3: Refactor only from observed failures**

For each failed expectation, record the verbatim response and failure class, patch only the instruction responsible, regenerate `openai.yaml`, rerun `quick_validate.py`, and repeat the failing fresh-context scenario. If all expectations pass, make no speculative additions.

- [ ] **Step 4: Run a real-repository forward-test**

Dispatch a fresh subagent with:

```text
Use $select-next-project-issue from /tmp/sheetlens-skill-stage/select-next-project-issue to select the one SheetLens issue I should handle now in /home/tonny/workspace/sheetlens. Do not modify any files. Return the skill's output contract and the commands' exit status.
```

Expected for the current clean state: `check` and `next` exit 0, and the selected issue matches the first candidate printed by a direct `next` run.

---

### Task 4: Install, verify, review, and commit

**Files:**
- Create: `.agents/skills/select-next-project-issue/SKILL.md`
- Create: `.agents/skills/select-next-project-issue/agents/openai.yaml`

**Interfaces:**
- Consumes: the validated staging directory from Task 3.
- Produces: the repository-local discoverable skill, verification evidence, and one focused commit.

- [ ] **Step 1: Confirm the destination is new and install the staged skill**

Run with explicit elevated write approval because `.agents` is mounted read-only in the managed sandbox:

```bash
test ! -e .agents/skills/select-next-project-issue
mkdir -p .agents/skills
cp -a /tmp/sheetlens-skill-stage/select-next-project-issue \
  .agents/skills/select-next-project-issue
```

Expected: destination contains only `SKILL.md` and `agents/openai.yaml`.

- [ ] **Step 2: Validate the installed artifact and existing project contracts**

Run:

```bash
python /home/tonny/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .agents/skills/select-next-project-issue
uv run python scripts/check_project_state.py check
uv run python scripts/check_project_state.py next
uv run pytest tests/test_project_state.py -q
uv run ruff check .
git diff --check
```

Expected: skill validation succeeds; `check` and `next` exit 0; project-state tests pass; Ruff and diff checks pass.

- [ ] **Step 3: Ask an independent reviewer to find problems**

Dispatch a reviewer with the approved design, installed skill directory, RED/GREEN evidence, and this instruction:

```text
Find requirement gaps, unsafe selection behavior, trigger problems, output-contract ambiguity, and missing test coverage. Do not merely confirm that it looks correct. Report findings with file and line references; make no changes.
```

Apply verified findings through the staging copy first, rerun the affected forward-test and validators, then reinstall the two generated files with approval.

- [ ] **Step 4: Consult Advisor before completion**

Ask Advisor whether the installed skill satisfies the approved solo sequential selection contract and whether verification evidence leaves a material gap. If Advisor is unavailable, record the exact failure and continue with independent review plus direct verification evidence.

- [ ] **Step 5: Commit the installed skill**

Run:

```bash
git add .agents/skills/select-next-project-issue/SKILL.md \
  .agents/skills/select-next-project-issue/agents/openai.yaml
git commit -m "feat: add next project issue skill"
```

- [ ] **Step 6: Verify the committed state**

Run:

```bash
git status --short
git show --stat --oneline --decorate HEAD
```

Expected: worktree is clean and HEAD contains only the two skill files from this task.
