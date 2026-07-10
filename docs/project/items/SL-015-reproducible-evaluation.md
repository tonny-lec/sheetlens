---
id: SL-015
title: 再現可能な A/B 評価基盤
status: proposed
priority: P1
type: quality
milestone: M4
depends_on:
  - SL-001
  - SL-003
touches:
  - eval
  - tests/test_eval_dummy.py
  - README.md
owner: null
---

# SL-015 再現可能な A/B 評価基盤

## 背景と根本原因

A/B 評価は手動セッションと主観的な「明確に上回る」判定で、モデル、prompt、試行数、rubric、閾値を再現できない。

## 根拠

`eval/README.md:10-20`、`README.md:113`。

## 受け入れ条件

- [ ] 評価 manifest、固定 prompt、モデル設定、複数試行、rubric、閾値、結果 JSON/Markdown schema を定義する。
- [ ] 構造層だけでなく意味層 QA と負例を含める。
- [ ] 欠損回答も採点する。

## 対象外

特定 LLM ベンダーへの固定と本番業務データの収集。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
