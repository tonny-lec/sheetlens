---
id: SL-005
title: 名前定義プルダウンの解決
status: ready
priority: P1
type: defect
milestone: M2
depends_on: []
touches:
  - src/sheetlens/reader/features.py
  - src/sheetlens/reader/workbook.py
  - tests/test_features.py
owner: null
---

# SL-005 名前定義プルダウンの解決

## 背景と根本原因

`_resolve_list` は `=Choices` を現在シートのセル参照として扱い、解決失敗を空配列へ潰す。

## 根拠

`src/sheetlens/reader/features.py:4-23`、`src/sheetlens/reader/workbook.py:56-60`。有効な名前定義でも `choices=[]` を親監査で再現済み。

## 受け入れ条件

- [ ] workbook scope と sheet-local scope、引用シート名を解決する。
- [ ] 未解決名、INDIRECT、OFFSET は gap にする。
- [ ] 各ケースのテストを追加する。

## 対象外

任意の動的 Excel 式を完全評価すること。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
