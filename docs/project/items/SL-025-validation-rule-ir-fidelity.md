---
id: SL-025
title: 入力規則 IR の意味情報完全化
status: proposed
priority: P1
type: defect
milestone: M2
depends_on: [SL-005]
touches:
  - src/sheetlens/model/ir.py
  - src/sheetlens/reader/features.py
  - src/sheetlens/formulas.py
  - src/sheetlens/renderers/markdown.py
  - tests/test_ir.py
  - tests/test_features.py
  - tests/test_formulas.py
  - tests/test_markdown.py
owner: null
---

# SL-025 入力規則 IR の意味情報完全化

## 背景と根本原因

入力規則の IR は `formula1` と list の選択肢だけを保持し、`formula2`、`operator`、入力・エラー制御属性を捨てている。例えば `between 1 and 10` は上限が無警告で欠落し、AI 向け構造情報が実際の Excel 条件と異なる。

## 根拠

`src/sheetlens/model/ir.py` の `ValidationRule` と `src/sheetlens/reader/features.py` の `read_validations()` は `formula1` だけを IR 化する。`between` の fixture を抽出すると `formula1=1` のみが残り、`formula2=10` は `extraction_gaps` にも記録されない。

## 受け入れ条件

- [ ] `formula1`、`formula2`、`operator`、主要な入力・エラー制御属性を型付き IR として保持する。
- [ ] `between`、`notBetween`、list、日付・時刻・文字列長などの代表的な規則を raw JSON と Markdown へ忠実に伝播する。
- [ ] 入力規則の formula1/formula2 と名前定義・セル範囲の依存を dependency edge へ反映する。
- [ ] 未対応属性を無警告で捨てず、規則単位の `extraction_gaps` として記録する。
- [ ] empty range と解決失敗を区別し、既存の SL-005 の list 解決互換性を維持する。

## 対象外

任意の動的 Excel 式を評価する計算エンジン、入力規則 UI の完全な再現。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に規則種別ごとの fixture、raw JSON、Markdown、dependency edge、gap の検証結果を記録する。
