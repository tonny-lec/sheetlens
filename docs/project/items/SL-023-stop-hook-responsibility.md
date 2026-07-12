---
id: SL-023
title: Stop hook の責務境界と最小完了ゲート
status: ready
priority: P1
type: quality
milestone: M4
depends_on: [SL-020, SL-021, SL-022]
touches:
  - .codex/hooks/stop_git_completion.py
  - tests/test_git_completion_hook.py
  - .agents/skills/finish-project-issue/SKILL.md
  - docs/project/items/SL-023-stop-hook-responsibility.md
  - docs/project/backlog.md
owner: null
---

# SL-023 Stop hook の責務境界と最小完了ゲート

## 背景と根本原因

現在の Stop hook は、完了宣言時に branch、dirty worktree、project-state、active issue を確認する
Git 完了ゲートである。一方、今回の実証では、finish skill が利用できない状況での status 更新や、
hook がどこまで責務を持つべきかが曖昧だった。責務を先に分解せずに検証項目を追加すると、hook の
複雑化と別経路との判定重複を招くため、拡張ではなく責務境界の見直しから行う。

## 根拠

`.codex/hooks/stop_git_completion.py`、`tests/test_git_completion_hook.py`、
`.codex/hooks.json`、SL-020〜SL-022 で整理する完了状態・直列化・owner の契約。

## 受け入れ条件

- [ ] Stop hook、finish skill、project-state validator の責務と、各責務が持たない判定を重複なく定義する。
- [ ] 現行の安全性を下げず、hook に追加する処理と追加しない処理を根拠付きで決定する。責務拡張をしない結論も許容する。
- [ ] 最小の代表ケースで、完了宣言を許可・阻止すべき境界を検証し、hook の複雑度と呼び出し回数を増やさずトークン使用量を削減できるかを代理指標で比較する。
- [ ] 最も重要な不確実性を「どの完了条件を hook が保証すべきか」と明示し、既存 hook と finish skill の境界だけを検証する最小ケースを定義する。

## 対象外

`.git` read-only の原因解決、config の例外対応、remote 操作、無条件の pytest/Ruff 実行追加、
Stop hook への責務の無制限な集約。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に責務分担表、拡張または非拡張の判断根拠、最小境界ケース、品質・トークン使用量の代理指標、
検証結果を記録する。
