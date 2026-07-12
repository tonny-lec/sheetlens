---
id: SL-022
title: owner と status のライフサイクル再設計
status: ready
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

- [ ] 各 status 遷移で owner が誰により設定・維持・解放されるか、失敗・中断・再開を含めて表にする。
- [ ] `in_progress` の再開、`blocked` への遷移、`done` への完了、完了失敗からの復旧を、owner と一体で validator/test で検証する。
- [ ] owner の不整合を、状態をさらに壊さずに修復できる最小手順を workflow に定義する。
- [ ] 既存の所有権・並行実行の安全性を維持しながら、重複した状態確認や説明出力を減らせるかを代理指標で比較する。
- [ ] 最も重要な不確実性を「中断後の再開主体と owner の一貫性」と明示し、最小の状態遷移ケースで確認する。

## 対象外

Codex の sandbox/approval 設定、`.git` read-only の原因、複数 owner による同一課題の共同編集、
外部タスク管理サービス。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に status/owner 遷移表、失敗復旧ケース、品質・トークン使用量の代理指標、検証結果を記録する。
