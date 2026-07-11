# Autonomous Git Completion Implementation Plan

**Goal:** Let Codex finish one SheetLens issue through verified local Git integration without a separate user request.

**Architecture:** Put durable decisions in repository `AGENTS.md`, fragile Git sequencing in a repo-local `finish-project-issue` Skill, and completion-claim enforcement in a read-only, loop-safe Stop hook. Keep remote and history-rewriting operations outside the automation boundary.

## Constraints

- Preserve the solo sequential issue workflow.
- Integrate only with `git merge --ff-only`.
- Stage explicit issue-owned paths and stop on unrelated changes.
- Reverify on `main`; task-branch verification alone is insufficient.
- Do not push, rebase, reset, force, or auto-resolve conflicts.
- Keep the hook read-only and permit the second Stop via `stop_hook_active`.

## Tasks

- [x] Add repository Git-autonomy guidance.
- [x] Add and validate the `finish-project-issue` Skill.
- [x] Add the project-local Stop hook and unit tests.
- [x] Run focused and full validation, then record completion evidence.
