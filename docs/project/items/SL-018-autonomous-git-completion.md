---
id: SL-018
title: Codexによる課題完了時の自動Git統合
status: done
priority: P1
type: quality
milestone: M4
depends_on: []
touches:
  - AGENTS.md
  - .agents/skills/finish-project-issue
  - .codex/hooks.json
  - .codex/hooks/stop_git_completion.py
  - tests/test_git_completion_hook.py
  - docs/project/items/SL-018-autonomous-git-completion.md
  - docs/project/backlog.md
  - docs/superpowers/plans/2026-07-11-autonomous-git-completion.md
owner: null
---

# SL-018 Codexによる課題完了時の自動Git統合

## 背景と根本原因

課題を実装した各セッションで、利用者が別途commitとmainへのmergeを依頼している。
課題完了条件とGit統合条件がCodexから機械的に参照できる契約になっていない。

## 根拠

既存の `select-next-project-issue` は着手課題を決めるが、完了後の検証、commit、local
merge、main上の再検証、branch cleanupを一貫して実行する対になるworkflowがない。

## 受け入れ条件

- [x] 課題完了時にCodexが自動でcommitとlocal fast-forward mergeを判断できる。
- [x] unrelated changes、検証失敗、非fast-forward、remote操作では安全に停止する。
- [x] main上の再検証と統合branchのcleanupを必須にする。
- [x] 未統合状態での明示的な実装完了宣言をloop-safeなStop hookで検出する。
- [x] Git判断規則、Skill、hookの構造と動作を機械テストする。

## 対象外

remoteへの自動push、PR作成、force操作、競合の自動解消、複数課題の同時統合。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-11-autonomous-git-completion.md) に従って進める。

## 完了証拠

- `uv run pytest tests/test_git_completion_hook.py -q`: 5 passed。
- `uv run pytest -q`: 424 passed。
- `uv run ruff check .`: PASS。
- skill creatorの `quick_validate.py`: `Skill is valid!`。
- `uv run python scripts/check_project_state.py check`: PASS。
- `python3 -m json.tool .codex/hooks.json`: PASS。
- `git diff --check`: PASS。
- 実Stop payloadで、未コミットかつ`in_progress`の状態をblockし、理由を返すことを確認した。
- 実hook起動で`uv` cacheのread-only依存を検出し、hook自身のPythonでproject-state
  checkerを直接実行するよう修正した。
- 新規または変更されたproject-local hookは、次回セッションで`/hooks`を開き、内容を
  reviewしてtrustする。trustされるまでCodexはhookをskipする。
- side conversationではsubagentが禁止されているため、forward-testは行わず、純粋関数の
  unit testと実hook processへのpayload入力で代替した。
