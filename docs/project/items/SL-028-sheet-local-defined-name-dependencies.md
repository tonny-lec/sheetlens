---
id: SL-028
title: シートローカル定義名の依存解析
status: proposed
priority: P1
type: defect
milestone: M3
depends_on: [SL-012]
touches:
  - src/sheetlens/model/ir.py
  - src/sheetlens/reader/workbook.py
  - src/sheetlens/formulas.py
  - src/sheetlens/renderers/machine.py
  - tests/test_reader.py
  - tests/test_formulas.py
  - tests/test_machine.py
owner: null
---

# SL-028 シートローカル定義名の依存解析

## 背景と根本原因

Workbook スコープの定義名は依存解析へ渡されるが、シートローカル定義名は IR と parser の名前空間に保存されない。そのため、同じ名前をシートごとに異なる範囲へ割り当てる Excel の数式を、参照元シートに基づいて解決できない。

## 根拠

`src/sheetlens/reader/workbook.py` は `wb_f.defined_names` だけを収集し、`src/sheetlens/formulas.py` の `_DependencyParser` も Workbook 単位の辞書だけを参照する。シートローカル名 `LocalChoice` を使う数式は、定義が存在しても `unresolved` edge になる。

## 受け入れ条件

- [ ] Workbook スコープと sheet-local スコープを区別して IR と raw JSON に保存する。
- [ ] 数式元シートを基準に local name を優先し、未解決時だけ Workbook name を解決する。
- [ ] 同名定義、循環定義、欠損参照、外部参照を決定的に `unresolved` として保持する。
- [ ] cell、validation、conditional format の依存 edge と manifest の sheet dependencies へ結果を伝播する。
- [ ] 既存の Workbook name、外部 Workbook、case-insensitive 解決の互換性を維持する。

## 対象外

任意の Excel 式を評価する計算エンジン、動的な `INDIRECT`・`OFFSET` の完全解決。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に scope ごとの定義名 fixture、循環・欠損ケース、raw JSON、dependency edge、manifest の結果を記録する。
