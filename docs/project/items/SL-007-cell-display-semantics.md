---
id: SL-007
title: セルの型、表示形式、表示意味の保持
status: ready
priority: P1
type: enhancement
milestone: M2
depends_on: []
touches:
  - src/sheetlens/model/ir.py
  - src/sheetlens/reader/workbook.py
  - src/sheetlens/renderers/markdown.py
  - tests/test_ir.py
  - tests/test_reader.py
  - tests/test_markdown.py
owner: null
---

# SL-007 セルの型、表示形式、表示意味の保持

## 背景と根本原因

Cell は value と formula だけで、数値が百分率、通貨、日付、先頭ゼロ付きコードのどれかを表現できない。

## 根拠

`src/sheetlens/model/ir.py:8-11`、`src/sheetlens/reader/workbook.py:12-15`。

## 受け入れ条件

- [ ] value_type、number_format、必要最小限の display_semantics を保持する。
- [ ] percentage、currency、date/time、leading-zero、Excel error の JSON と Markdown をテストする。

## 対象外

Excel の完全な見た目再現とフォント・罫線の全抽出。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
