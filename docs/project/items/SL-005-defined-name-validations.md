---
id: SL-005
title: 名前定義プルダウンの解決
status: done
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

- [x] workbook scope と sheet-local scope、引用シート名を解決する。
- [x] 未解決名、INDIRECT、OFFSET は gap にする。
- [x] 各ケースのテストを追加する。

## 対象外

任意の動的 Excel 式を完全評価すること。

## 実装計画

設計は
[`2026-07-11-defined-name-validations-design.md`](../../superpowers/specs/2026-07-11-defined-name-validations-design.md)
に記録した。実装は
[`2026-07-11-defined-name-validations.md`](../../superpowers/plans/2026-07-11-defined-name-validations.md)
に従う。

## 完了証拠

- focused: `uv run pytest tests/test_features.py -q` — `23 passed in 0.47s`
- full: `uv run pytest -q` — `374 passed in 1.90s`
- lint: `uv run ruff check .` — `All checks passed!`
- project state: `uv run python scripts/check_project_state.py check` — exit 0
- final whole-branch review: `Ready to merge: Yes`、Critical / Important / Minor すべてなし
