---
id: SL-021
title: 管理状態更新の直列化
status: done
priority: P1
type: quality
milestone: M4
depends_on: []
touches:
  - .agents/skills/finish-project-issue/SKILL.md
  - .agents/skills/process-project-backlog/SKILL.md
  - .agents/skills/promote-ready-project-issues/SKILL.md
  - .agents/skills/promote-ready-project-issues/agents/openai.yaml
  - docs/project/README.md
  - docs/superpowers/plans/2026-07-12-ready-promotion-harness.md
  - docs/project/items/SL-021-sequential-state-updates.md
  - docs/project/backlog.md
  - scripts/check_project_state.py
  - scripts/promote_ready_issues.py
  - tests/test_promote_ready_issues.py
owner: null
---

# SL-021 管理状態更新の直列化

## 背景と根本原因

今回の完了処理で `render` と `check` を並列実行したため、backlog の再生成途中を `check` が
読み、実際の状態不整合ではない一時的な失敗が発生した。状態を書き換える処理と、その結果に
依存する検証処理の実行順序を明示し、並列化してよい処理との境界を定義する必要がある。

## 根拠

`docs/project/README.md` の生成物更新に関する直列実行規則、
`.agents/skills/finish-project-issue/SKILL.md` の render/check 手順、今回の一時的な
backlog 同期エラー。

## 受け入れ条件

- [x] `render -> check`、status/owner 更新 -> render、commit -> merge -> main 再検証の依存順序を workflow に明記する。
- [x] 依存する状態更新・生成・検証を並列実行しないことを、skill の手順と代表的な forward test で検証する。
- [x] 独立した read-only 検証だけを並列化できる境界を定義し、品質を下げずにトークン使用量・ツール往復を削減できるかを代理指標で比較する。
- [x] 最も重要な不確実性を「生成途中の状態を検証が観測しないこと」と明示し、render/check の競合を再現する最小ケースで確認する。

## 対象外

実装課題の並列化、subagent の並列実行方針、`.git` read-only、remote 操作。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-12-ready-promotion-harness.md) に従って進める。

## 完了証拠

- `process-project-backlog` は通常完了時だけ `$promote-ready-project-issues` を一度呼び出し、
  issue 上限・blocker・検証失敗時には呼び出さない接続を追加した。
- `scripts/promote_ready_issues.py` は `check` の候補 ID を明示的に受け取り、clean `main`・
  active issue なしを確認して status 更新を行い、`render -> check` を直列実行する。
- 更新、render、check のテストを追加し、render 失敗時に issue ファイルと backlog を元へ復元する
  ケースを確認した。既存 validator の判定関数は公開 API 経由で再利用した。
- 代理指標を同一 forward case で比較した結果、依存列は `check -> render -> check` の 3 呼出しで、
  並列・重複 write は 0 件だった。read-only の 4 検証（pytest、ruff、project-state check、diff check）は
  4 コマンドのままだが、同一スナップショットを 1 orchestration にまとめられるため、親側の往復は
  4 回から 1 回へ削減できる。process skill は 64 行から 73 行（追加は handoff 9 行）に留め、
  昇格ロジックの重複を作っていない。
- handoff forward test で、clean `main` 上の昇格、明示 path の staging、state-only commit、
  project-state check、clean worktree を確認した。
- `uv run pytest -q`（478 passed、既存の ZipFile deallocator warning 1 件）、
  `uv run ruff check .`、`uv run python scripts/check_project_state.py check`、
  `git diff --check` が成功した。
