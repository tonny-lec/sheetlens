---
name: finish-project-issue
description: Use when one SheetLens project issue has satisfied its acceptance criteria and Codex must verify, commit, locally fast-forward merge it into main, reverify, and clean up under the solo sequential workflow.
---

# Finish Project Issue

## Overview

Finish exactly one active SheetLens issue without requiring a separate commit or merge request.
Stop rather than guessing whenever scope, history, or integration safety is ambiguous.

`done` is authoritative only after this workflow has committed the issue, fast-forwarded it into
local `main`, rerun the required verification on `main`, and confirmed a clean worktree with no
active issue. The `done` value recorded in the task-branch commit is provisional until those steps
complete. Only the parent/root finish workflow may make that transition; implementation work must
not independently mark an issue `done`.

The lifecycle invariant is `in_progress + non-empty owner`; `blocked`, `ready`, `done`, and
`cancelled` release owner to `null`. A post-merge verification recovery is the only `done ->
in_progress` exception and must set `owner: Codex` in the same recovery update. Any `blocked ->
in_progress` resume must establish the new owner at the same time as status.

## User Overrides

Do not commit or merge when the user requests verification only, no commit, no merge, or
read-only review. Never push unless the user explicitly requests it.

## Workflow

1. Run `uv run python scripts/check_project_state.py check`. Stop on nonzero exit.
2. Read `docs/project/backlog.md`. Require exactly one `in_progress` issue and resolve exactly
   one matching `docs/project/items/SL-NNN-*.md`.
3. Read the issue. Require every acceptance checkbox checked, a real implementation-plan link,
   non-placeholder completion evidence, and an accurate `touches` list.
4. Inspect `git status --short`, `git diff --name-only`, `git diff --cached --name-only`, and
   untracked files. Stop if any change is unrelated to the issue or ownership is uncertain.
5. Run all required verification commands from the repository `AGENTS.md`. Fix failures and
   rerun; never suppress failures to reach commit.
6. As the provisional task-branch payload, change the issue to `status: done`, set `owner: null`,
   render the backlog, and rerun the project-state check. Include those files in the issue scope.
   Do not declare completion at this point. If this workflow is interrupted before the commit,
   update the uncommitted item back to `in_progress` with `owner: Codex`, or use `blocked` with
   `owner: null`, the required blocker fields, and the resume condition; render/check before
   stopping. Never independently leave `done` on `main`.
7. Establish a task branch:
   - On `main` with the task changes present, create `feat/SL-NNN-<short-slug>` before staging.
   - On detached HEAD, create that branch.
   - On an existing task branch, keep it only when it clearly belongs to the active issue.
   - Stop if the branch belongs to another issue or is checked out in an incompatible worktree.
8. Stage explicit issue-owned paths only. Never use `git add -A`, `git add .`, or broad globs.
   Review `git diff --cached --check` and `git diff --cached --stat` before committing.
9. Create one intentional commit using the repository's style. Record the commit ID.
10. Switch to `main` and run `git merge --ff-only <task-branch>`. Stop if `main` moved,
    fast-forward is impossible, or a conflict/rebase would be required.
11. On `main`, rerun all required verification commands and confirm `git status --short` is
    empty. Do not trust only the task-branch results. If post-merge verification fails, do not
    reset or rewrite history: keep the merged commit, set the issue back to `in_progress` or
    `blocked` (`owner: Codex` for `in_progress`, `owner: null` for `blocked`), record the failure
    and resume condition, render/check, and make a state-only recovery commit on `main`.
12. Delete the merged local branch with `git branch -d`. Do not delete a branch with `-D`. If only
    branch deletion fails after main integration, verification, clean state, and no active issue
    have succeeded, preserve `done` and report the remaining cleanup condition.

## Stop Conditions

- Multiple or zero active issues before the status transition.
- Unrelated or unexplained worktree changes.
- A failed verification command.
- A non-fast-forward merge, concurrent `main` movement, conflict, or required history rewrite.
- An unfinished task branch or provisional `done` state that cannot be safely resumed.
- Missing approval for a required Git metadata write.
- Any remote operation not explicitly authorized by the user.

Preserve all work, report the exact blocker, and leave the branch available for recovery.

## Output Contract

Return these fields after successful local integration:

```text
実装完了
課題: SL-NNN 課題名
コミット: <sha> <subject>
統合: main / fast-forward
検証: <commands and results>
作業ツリー: clean
リモート: 未送信 | 明示依頼により送信済み
```
