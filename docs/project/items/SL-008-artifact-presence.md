---
id: SL-008
title: グラフ、図形、ピボット等の存在記録
status: ready
priority: P1
type: enhancement
milestone: M2
depends_on: []
touches:
  - src/sheetlens/model/ir.py
  - src/sheetlens/reader/workbook.py
  - src/sheetlens/renderers/machine.py
  - tests/test_reader.py
  - tests/test_machine.py
owner: null
---

# SL-008 グラフ、図形、ピボット等の存在記録

## 背景と根本原因

charts、drawings、pivots の存在を保持する IR がなく、「存在しない」と「未抽出」を区別できない。

## 根拠

`src/sheetlens/model/ir.py:53-61`、`docs/superpowers/specs/2026-07-07-sheetlens-design.md:198-204`。

## 受け入れ条件

- [ ] シート別の artifact type、件数、OOXML part を保存する。
- [ ] 詳細未対応は gap として manifest に出す。
- [ ] chart、image/shape、pivot part をテストする。

## 対象外

グラフ系列、図形レイアウト、ピボット定義の完全解析。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
