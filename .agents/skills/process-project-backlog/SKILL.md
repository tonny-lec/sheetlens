---
name: process-project-backlog
description: Process SheetLens project backlog issues autonomously and sequentially from validated selection through research, design, implementation, verification, and local integration. Use when the user asks Codex to work through, drain, automatically handle, or continue the repository backlog; invoke explicitly for multi-issue execution.
---

# Process Project Backlog

Process one issue at a time and use the repository's project files as the only durable state.
Continue until no eligible issue remains, the user-supplied issue limit is reached, or a stop
condition occurs.

## Loop

1. Run `uv run python scripts/check_project_state.py check`. Stop on nonzero exit.
2. Inspect `git status --short --branch` and the current branch.
   Also inspect unmerged task branches with `git branch --no-merged main 'feat/SL-*'`.
   If exactly one branch maps unambiguously to an unfinished issue, resume that branch and its
   finish workflow; do not invoke selection or start another issue. If multiple or ambiguous
   task branches exist, stop and report the branches and the evidence needed to resume.
3. Invoke `$select-next-project-issue` and use only its validated result.
   Keep every project-management state update in the root agent; never delegate it.
   - Treat `着手可能な課題なし` as successful completion.
   - Continue the single `in_progress` issue; never select another issue beside it.
   - For a new issue, require clean `main`, set only that issue to `in_progress`, set
     `owner: Codex`, render the backlog, and rerun the state check.
   - The parent owns every status/owner transition and updates the pair in one item write before
     running `render -> check`. Use `owner: null` for `blocked`, `done`, `ready`, `proposed`, and
     `cancelled`; assign a non-empty owner whenever entering `in_progress`.
   - For `blocked -> in_progress`, verify the resuming owner, branch, worktree, and scope before
     setting both fields. Never reopen by changing status alone.
4. Read the issue and relevant repository evidence. Finish information collection and design
   before editing implementation files.
   - Confirm the root cause, acceptance criteria, scope, dependencies, and current behavior.
   - Create or update the issue's implementation plan under `docs/superpowers/plans/`.
   - Update the issue's `touches` and plan link, render, and check before implementation.
   - Stop for user direction when a material product or scope decision is unresolved.
5. Implement the smallest end-to-end change that satisfies the active issue. Follow applicable
   repository instructions and skills. Do not start or parallelize another project issue.
6. Verify the implementation against every acceptance criterion. Fix failures without
   suppressing them. Update the acceptance checkboxes and completion evidence only from actual
   results.
7. Invoke `$finish-project-issue`. Do not reproduce its Git workflow or weaken its stop
   conditions.
8. Before another iteration, require all of the following:
   - current branch is `main`;
   - `git status --short` is empty;
   - `uv run python scripts/check_project_state.py check` exits zero;
   - no issue is `in_progress`.
   - no unmerged `feat/SL-*` task branch remains.
9. Repeat from step 1 unless the requested issue limit has been reached.

## Post-completion handoff

When the loop ends normally because `$select-next-project-issue` reports `着手可能な課題なし`,
and the clean-main, project-state, and no-active-issue checks in step 8 pass, invoke
`$promote-ready-project-issues` once. Do not invoke it after an issue limit, blocker, failed
verification, invalid state, or another stop condition. The handoff owns only proposed-to-ready
promotion and its state-only persistence; it must not select or start a newly ready issue in the same
invocation.

## Resume Rules

- Resume an existing `in_progress` issue only when its owner, branch, and worktree changes are
  clearly related to that issue.
- If ownership must change during resume, record an explicit handoff basis before the atomic
  status/owner update; do not silently overwrite an unrelated owner.
- Preserve related partial work and continue from the first unmet acceptance criterion.
- Stop when ownership or change scope is ambiguous. Report the evidence needed to resume.
- Keep no skill-specific state, queue, log, or checkpoint file.

## Stop Conditions

Stop immediately without selecting another issue when any of these occurs:

- invalid project state or multiple `in_progress` issues;
- unrelated or ownership-ambiguous worktree changes;
- unclear scope, acceptance criteria, plan, or required external input;
- a required permission or user decision is unavailable;
- repeated failure after attempted correction;
- failed required verification;
- conflict, non-fast-forward integration, concurrent `main` movement, or incomplete finish;
- post-finish branch, worktree, project-state, or active-issue checks fail.
- a provisional `done` task branch remains and cannot be resumed safely before selection.

Return the completed issue IDs, the current blocker or normal stop reason, and the exact condition
for resuming. Never push, force, rebase, reset, or resolve ambiguous conflicts automatically.
