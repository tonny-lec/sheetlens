---
name: finish-project-issue
description: Use when one SheetLens project issue has satisfied its acceptance criteria and Codex must verify, commit, locally fast-forward merge it into main, reverify, and clean up under the solo sequential workflow.
---

# Finish Project Issue

## Overview

Finish exactly one active SheetLens issue without requiring a separate commit or merge request.
Stop rather than guessing whenever scope, history, or integration safety is ambiguous.

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
6. Change the issue to `status: done`, set `owner: null`, render the backlog, and rerun the
   project-state check. Include those files in the issue scope.
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
    empty. Do not trust only the task-branch results.
12. Delete the merged local branch with `git branch -d`. Do not delete a branch with `-D`.

## Stop Conditions

- Multiple or zero active issues before the status transition.
- Unrelated or unexplained worktree changes.
- A failed verification command.
- A non-fast-forward merge, concurrent `main` movement, conflict, or required history rewrite.
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
