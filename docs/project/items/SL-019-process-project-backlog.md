---
id: SL-019
title: backlog 課題の自動直列処理
status: done
priority: P2
type: enhancement
milestone: M4
depends_on: []
touches:
  - .agents/skills/process-project-backlog
  - docs/project/items/SL-019-process-project-backlog.md
  - docs/project/backlog.md
  - docs/superpowers/plans/2026-07-11-process-project-backlog.md
owner: null
---

# SL-019 backlog 課題の自動直列処理

## 背景と根本原因

課題の選定と完了には個別の skill があるが、選定、情報収集、設計、実装、完了、次課題への
遷移を一度の明示起動で安全に繰り返す workflow がない。

## 根拠

`.agents/skills/select-next-project-issue/SKILL.md` と
`.agents/skills/finish-project-issue/SKILL.md` は、それぞれ選定と完了だけを扱う。

## 受け入れ条件

- [x] 明示起動により active 課題の継続、または最上位 ready 課題の着手を一意に行う。
- [x] 各課題で情報収集と設計を終えてから実装し、常に一課題だけを処理する。
- [x] 完了時は既存 finish skill を使い、clean な main を確認してから次へ進む。
- [x] 異常、曖昧さ、承認待ちでは状態を壊さず停止し、理由と再開条件を返す。
- [x] skill validator と隔離した代表ケースで workflow を検証する。

## 対象外

無人の `codex exec` runner、scheduler、並列処理、remote 操作、独自状態ファイル。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-11-process-project-backlog.md) に従って進める。

## 完了証拠

- skill creator `quick_validate.py`: `Skill is valid!`。
- 隔離 forward test: active 課題では `SL-019` を継続し、空 backlog は正常終了、
  backlog 不整合は変更せず停止した。
- 新規着手 forward test: clean な `main` では最上位の `SL-010` を選び、unrelated な
  dirty worktree では変更せず停止した。
- advisor review: 新規着手分岐と root-only 管理を追加後、他に MVP を妨げる問題なし。
- `uv run pytest -q`: 436 passed。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
