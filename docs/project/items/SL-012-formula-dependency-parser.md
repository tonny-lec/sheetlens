---
id: SL-012
title: 数式正規化と依存グラフの token 解析化
status: done
priority: P2
type: refactor
milestone: M3
depends_on: []
touches:
  - src/sheetlens/formulas.py
  - src/sheetlens/detectors/formula_patterns.py
  - src/sheetlens/renderers/machine.py
  - src/sheetlens/model/ir.py
  - tests/test_formulas.py
  - tests/test_formula_patterns.py
  - tests/test_extract_e2e.py
  - tests/test_ir.py
  - tests/test_machine.py
  - docs/project/items/SL-012-formula-dependency-parser.md
  - docs/project/backlog.md
  - docs/superpowers/plans/2026-07-11-formula-dependency-parser.md
owner: null
---

# SL-012 数式正規化と依存グラフの token 解析化

## 背景と根本原因

数式正規化と依存検出が文字列正規表現中心で、lowercase、引用シート名、外部同名シート、defined name を誤分類する。

## 根拠

`src/sheetlens/detectors/formula_patterns.py:10-11`、`:28-55`、`src/sheetlens/renderers/machine.py:9-38`。

## 受け入れ条件

- [x] Excel tokenizer とセル位置基準の相対参照で正規化する。
- [x] 依存を source、target_workbook、target_sheet、target_range、unresolved の edge として保存する。
- [x] 外部同名シート、defined name、validation/CF 参照をテストする。

## 対象外

Excel 計算エンジンの実装。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-11-formula-dependency-parser.md) に従って進める。

## 完了証拠

- `uv run pytest tests/test_formulas.py tests/test_formula_patterns.py tests/test_machine.py
  tests/test_ir.py tests/test_extract_e2e.py -q`: 47 passed。
- `uv run pytest -q`: 453 passed。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
- R1C1相当の相対正規化、local/external同名sheet分離、quoted sheet、defined name cycle、
  validation/CF、3D/structured/tokenize failureをedgeとして検証した。
- advisor reviewの指摘によりmulti-cell相対参照をunresolvedへ修正し、path付き外部参照と
  外部defined nameのbook identityを保持した。再レビューでblocking findingなし。
