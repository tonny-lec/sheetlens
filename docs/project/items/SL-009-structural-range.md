---
id: SL-009
title: structural range と非表示範囲の修正
status: ready
priority: P2
type: defect
milestone: M2
depends_on: []
touches:
  - src/sheetlens/model/ir.py
  - src/sheetlens/reader/workbook.py
  - src/sheetlens/detectors/questions.py
  - tests/test_reader.py
  - tests/test_questions.py
owner: null
---

# SL-009 structural range と非表示範囲の修正

## 背景と根本原因

used_range は値セルだけから求められ、空の結合・入力規則・条件付き書式を無視する。グループ化された非表示列は先頭キーだけ記録する。

## 根拠

`src/sheetlens/reader/workbook.py:37-38`、`:69`、`:72`。

## 受け入れ条件

- [ ] content range と structural range を分離する。
- [ ] 結合、入力規則、条件付き書式を structural range に含める。
- [ ] B:D のグループ非表示を全範囲として保存する。

## 対象外

書式だけが無制限に設定されたシートの全セル展開。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
