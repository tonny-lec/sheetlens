---
id: SL-012
title: 数式正規化と依存グラフの token 解析化
status: ready
priority: P2
type: refactor
milestone: M3
depends_on: []
touches:
  - src/sheetlens/detectors/formula_patterns.py
  - src/sheetlens/renderers/machine.py
  - src/sheetlens/model/ir.py
  - tests/test_formula_patterns.py
  - tests/test_machine.py
owner: null
---

# SL-012 数式正規化と依存グラフの token 解析化

## 背景と根本原因

数式正規化と依存検出が文字列正規表現中心で、lowercase、引用シート名、外部同名シート、defined name を誤分類する。

## 根拠

`src/sheetlens/detectors/formula_patterns.py:10-11`、`:28-55`、`src/sheetlens/renderers/machine.py:9-38`。

## 受け入れ条件

- [ ] Excel tokenizer とセル位置基準の相対参照で正規化する。
- [ ] 依存を source、target_workbook、target_sheet、target_range、unresolved の edge として保存する。
- [ ] 外部同名シート、defined name、validation/CF 参照をテストする。

## 対象外

Excel 計算エンジンの実装。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
