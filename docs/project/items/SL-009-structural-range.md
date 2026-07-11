---
id: SL-009
title: structural range と非表示範囲の修正
status: done
priority: P2
type: defect
milestone: M2
depends_on: []
touches:
  - src/sheetlens/model/ir.py
  - src/sheetlens/reader/workbook.py
  - src/sheetlens/renderers/machine.py
  - src/sheetlens/renderers/markdown.py
  - src/sheetlens/annotations/schema.py
  - tests/test_ir.py
  - tests/test_reader.py
  - tests/test_machine.py
  - tests/test_markdown.py
  - tests/test_annotations.py
  - tests/test_questions.py
  - docs/superpowers/plans/2026-07-11-structural-range.md
  - docs/project/items/SL-009-structural-range.md
  - docs/project/backlog.md
owner: null
---

# SL-009 structural range と非表示範囲の修正

## 背景と根本原因

used_range は値セルだけから求められ、空の結合・入力規則・条件付き書式を無視する。グループ化された非表示列は先頭キーだけ記録する。

## 根拠

`src/sheetlens/reader/workbook.py:37-38`、`:69`、`:72`。

## 受け入れ条件

- [x] content range と structural range を分離する。
- [x] 結合、入力規則、条件付き書式を structural range に含める。
- [x] B:D のグループ非表示を全範囲として保存する。

## 対象外

書式だけが無制限に設定されたシートの全セル展開。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-11-structural-range.md) に従って進める。

## 完了証拠

- `uv run pytest tests/test_ir.py tests/test_reader.py tests/test_machine.py tests/test_markdown.py tests/test_annotations.py tests/test_questions.py -q`: 64 passed。
- `uv run pytest -q`: 436 passed。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
- 値・数式セルだけの content range と、生の結合・入力規則・条件付き書式を包含する
  structural range を分離し、意味抽出失敗時も構造範囲を保持するテストを追加した。
- `XFD1048576` の書式だけのセルを含む workbook で矩形走査が発生せず、内容・構造範囲が
  `A1:A1` のままであることを確認した。
- grouped `B:D` と `Z:AB` を `B, C, D, Z, AA, AB` の列番号順へ展開し、質問 target にも
  全列が反映されることを確認した。
- Advisor の問題探索レビューで、遠方書式セルの矩形走査、旧互換フィールドの代入不整合、
  structural/content の作成時・代入時不変条件、`None` 早期 return の未検証経路を検出し、
  すべて回帰テスト付きで修正した。相談上限到達後は親が最終差分を再点検し、追加の
  must-fix を認めなかった。
