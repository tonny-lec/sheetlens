---
id: SL-006
title: 条件付き書式 IR の完全化
status: in_progress
priority: P1
type: defect
milestone: M2
depends_on: []
touches:
  - src/sheetlens/model/ir.py
  - src/sheetlens/reader/features.py
  - tests/test_ir.py
  - tests/test_features.py
owner: codex
---

# SL-006 条件付き書式 IR の完全化

## 背景と根本原因

ConditionalFormat は式を 1 件しか保持せず、reader は先頭式だけを保存し、color scale 等の payload を捨てる。

## 根拠

`src/sheetlens/model/ir.py:21-26`、`src/sheetlens/reader/features.py:47-59`。between の第 2 式と color scale payload の欠落を親監査で再現済み。

## 受け入れ条件

- [ ] formulas 配列、colorScale、dataBar、iconSet、dxf の type 別 payload を保存する。
- [ ] 未対応型は gap にする。
- [ ] between、複数式 expression、全可視化型をテストする。

## 対象外

条件付き書式の画面レンダリング。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-11-conditional-format-ir.md) に従って進める。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
