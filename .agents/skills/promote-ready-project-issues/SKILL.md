---
name: promote-ready-project-issues
description: Promote validated proposed SheetLens issues to ready after process-project-backlog completes normally.
---

# Promote Ready Project Issues

Use this only as the post-completion handoff from `$process-project-backlog`. Do not invoke it when
the backlog loop stopped because of an issue limit, an invalid state, a blocker, failed verification,
or a required user decision.

1. From the repository root, run `uv run python scripts/promote_ready_issues.py check`.
2. If the command fails or prints no candidates, stop without changing files.
3. Inspect each printed candidate issue against its root cause, evidence, acceptance criteria,
   out-of-scope statement, touches, and completed dependencies. Pass exactly the confirmed IDs printed by `check` to
   `uv run python scripts/promote_ready_issues.py promote --ids <ID ...>`.
   The harness rechecks clean `main`, project state, and the absence of an active issue immediately
   before writing. It updates only the explicitly supplied candidate IDs, then runs `render -> check`.
4. If promotion fails, stop and preserve the reported failure. The harness restores all affected item
   files and `backlog.md` when its write/render/check transaction fails.
5. Run `git diff --check`, stage only the promoted issue files and `docs/project/backlog.md`, and create
   one state-only commit such as `docs(project): promote eligible issues to ready`. Rerun the project
   state check and confirm the worktree is clean.

Do not select, implement, or start a newly ready issue in this handoff. The next invocation of
`$process-project-backlog` selects it. This skill owns only the connection and persistence of the
proposed-to-ready state transition; it does not replace backlog selection, implementation, or issue
completion.
