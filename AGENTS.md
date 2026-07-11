# SheetLens Repository Guidance

## Project issue workflow

- Treat `docs/project/items/*.md` as the source of truth and
  `docs/project/backlog.md` as generated output.
- Run `uv run python scripts/check_project_state.py check` before trusting project state.
- Keep exactly one issue `in_progress` under the solo sequential workflow.
- Associate material implementation work with that active issue. Update its `touches`,
  acceptance checkboxes, plan link, and completion evidence as the work changes.

## Git autonomy

- For tracked issue work, invoke `$finish-project-issue` automatically after the acceptance
  criteria are satisfied. The user does not need to separately request commit or local merge.
- Do not invoke it when the user requests verification only, no commit, no merge, or a review
  without changes.
- Keep one issue per branch and commit. Never combine unrelated dirty changes.
- Allow automatic local integration only through `git merge --ff-only` into `main`.
- Never automatically rebase, force-push, reset, rewrite history, delete an unmerged branch, or
  resolve an ambiguous conflict.
- Do not push to a remote unless the user explicitly requests it.
- If Git metadata writes require approval, request the narrow command-specific approval and
  continue after approval.
- Use the exact heading `実装完了` only after the finish skill has committed, merged, reverified
  on `main`, and cleaned up the integration branch.

## Required verification

Run these commands before commit and again on `main` after merge:

```text
uv run pytest -q
uv run ruff check .
uv run python scripts/check_project_state.py check
git diff --check
```
