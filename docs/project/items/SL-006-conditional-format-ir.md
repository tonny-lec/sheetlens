---
id: SL-006
title: 条件付き書式 IR の完全化
status: done
priority: P1
type: defect
milestone: M2
depends_on: []
touches:
  - src/sheetlens/model/ir.py
  - src/sheetlens/reader/features.py
  - src/sheetlens/reader/workbook.py
  - src/sheetlens/renderers/machine.py
  - src/sheetlens/renderers/markdown.py
  - tests/test_ir.py
  - tests/test_features.py
  - tests/test_machine.py
  - tests/test_markdown.py
  - tests/test_extract_e2e.py
owner: null
---

# SL-006 条件付き書式 IR の完全化

## 背景と根本原因

ConditionalFormat は式を 1 件しか保持せず、reader は先頭式だけを保存し、color scale 等の payload を捨てる。

## 根拠

`src/sheetlens/model/ir.py:21-26`、`src/sheetlens/reader/features.py:47-59`。between の第 2 式と color scale payload の欠落を親監査で再現済み。

## 受け入れ条件

- [x] formulas 配列、colorScale、dataBar、iconSet、dxf の type 別 payload を保存する。
- [x] 未対応型は gap にする。
- [x] between、複数式 expression、全可視化型をテストする。

## 対象外

条件付き書式の画面レンダリング。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-11-conditional-format-ir.md) に従って進める。

## 完了証拠

- `uv run pytest tests/test_ir.py tests/test_features.py tests/test_machine.py tests/test_markdown.py tests/test_extract_e2e.py -q`: 76 passed。
- `uv run pytest -q`: 399 passed。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- 独立レビューで、range/type の例外境界、後半 getter 失敗時の抽出済み payload 保持、bool cfvo の暗黙変換を検出し、回帰テスト付きで修正した。
- Advisor は完了前に呼び出したが、本文のない応答で追加指摘は得られなかった。
