---
id: SL-021
title: 管理状態更新の直列化
status: ready
priority: P1
type: quality
milestone: M4
depends_on: []
touches:
  - .agents/skills/finish-project-issue/SKILL.md
  - .agents/skills/process-project-backlog/SKILL.md
  - docs/project/README.md
  - docs/project/items/SL-021-sequential-state-updates.md
  - docs/project/backlog.md
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

- [ ] `render -> check`、status/owner 更新 -> render、commit -> merge -> main 再検証の依存順序を workflow に明記する。
- [ ] 依存する状態更新・生成・検証を並列実行しないことを、skill の手順と代表的な forward test で検証する。
- [ ] 独立した read-only 検証だけを並列化できる境界を定義し、品質を下げずにトークン使用量・ツール往復を削減できるかを代理指標で比較する。
- [ ] 最も重要な不確実性を「生成途中の状態を検証が観測しないこと」と明示し、render/check の競合を再現する最小ケースで確認する。

## 対象外

実装課題の並列化、subagent の並列実行方針、`.git` read-only、remote 操作。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に直列化した手順、並列化可能な範囲、競合再現ケース、検証結果を記録する。
