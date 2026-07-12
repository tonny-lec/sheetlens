---
id: SL-022
title: owner と status のライフサイクル再設計
status: done
priority: P1
type: quality
milestone: M4
depends_on: []
touches:
  - scripts/check_project_state.py
  - tests/test_project_state.py
  - .agents/skills/select-next-project-issue/SKILL.md
  - .agents/skills/process-project-backlog/SKILL.md
  - .agents/skills/finish-project-issue/SKILL.md
  - docs/project/README.md
  - docs/project/items/SL-022-owner-lifecycle.md
  - docs/project/backlog.md
  - docs/superpowers/plans/2026-07-12-owner-lifecycle.md
owner: null
---

# SL-022 owner と status のライフサイクル再設計

## 背景と根本原因

`in_progress` では owner が必須で、`done` では owner を null にする現在の規則自体は明確だが、
中断・再開・完了失敗時にどの主体が owner を設定し、いつ解放するかが workflow に十分結び付いて
いない。今回 `done` から `in_progress` へ戻す際にも owner を同時に設定しなかったため、管理状態の
修正が一度失敗した。

## 根拠

`scripts/check_project_state.py` の owner/status 検証、
`docs/project/README.md` の状態遷移、各 project skill の owner 更新手順、今回の SL-013 復旧時の
`owner: null` エラー。

## 受け入れ条件

- [x] 各 status 遷移で owner が誰により設定・維持・解放されるか、失敗・中断・再開を含めて表にする。
- [x] `in_progress` の再開、`blocked` への遷移、`done` への完了、完了失敗からの復旧を、owner と一体で validator/test で検証する。
- [x] owner の不整合を、状態をさらに壊さずに修復できる最小手順を workflow に定義する。
- [x] 既存の所有権・並行実行の安全性を維持しながら、重複した状態確認や説明出力を減らせるかを代理指標で比較する。
- [x] 最も重要な不確実性を「中断後の再開主体と owner の一貫性」と明示し、最小の状態遷移ケースで確認する。

## 対象外

Codex の sandbox/approval 設定、`.git` read-only の原因、複数 owner による同一課題の共同編集、
外部タスク管理サービス。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-12-owner-lifecycle.md) に従って進める。

## 完了証拠

- `uv run pytest tests/test_project_state.py -q`: 239 passed。
- `uv run pytest -q`: 504 passed、既存 xlsm テスト由来の warning 1件。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
- README と select/process/finish skills に、`in_progress` の owner 必須、blocked/done/ready/cancelled の
  owner null、blocked resume、done recovery、再オープン、cancel の遷移表と parent-only atomic update を記録した。
- validator は空白だけの owner を単一診断で拒否し、同一 item の blocked resume、blocked、done、done recovery、
  done -> ready、cancel をテストした。status-only resume は失敗する。
- 壊れた owner snapshot の check failure 後、対象 item write 1回、render 1回、check 1回で復旧し、
  途中の invalid state を再検証しない proxy metric を固定した。既存の parallel owner/touches 検証も504件で維持した。
- advisor と reviewer の指摘（blocked owner null、same-item transitions、atomic write instrumentation、
  recovery graph、cancel scope）を反映した。
