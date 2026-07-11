---
id: SL-007
title: セルの型、表示形式、表示意味の保持
status: done
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

- [x] value_type、number_format、必要最小限の display_semantics を保持する。
- [x] percentage、currency、date/time、leading-zero、Excel error の JSON と Markdown をテストする。

## 対象外

Excel の完全な見た目再現とフォント・罫線の全抽出。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-11-cell-display-semantics.md) に従って進める。

## 完了証拠

- `uv run pytest tests/test_reader.py tests/test_ir.py tests/test_markdown.py -q`: 22 passed。
- `uv run pytest -q`: 403 passed。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
- 独立レビューで、キャッシュ値のない数式セル、大文字の日付書式、固定桁の誤判定、
  locale 通貨 token、Markdown code span の空白保持を検出し、回帰テスト付きで修正した。
- Advisor は計画前と完了前に呼び出した。計画前の指摘を設計とテストへ反映し、
  完了前レビューは本文なしで追加指摘はなかった。
