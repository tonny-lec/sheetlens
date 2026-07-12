---
id: SL-002
title: kind 別注釈スキーマと重複シート処理
status: done
priority: P1
type: defect
milestone: M1
depends_on: [SL-001]
touches:
  - src/sheetlens/annotations/schema.py
  - src/sheetlens/pipeline.py
  - src/sheetlens/cli.py
  - src/sheetlens/renderers/markdown.py
  - tests/test_annotations.py
  - tests/test_compile_e2e.py
  - tests/test_check_e2e.py
  - tests/test_markdown.py
  - docs/project/items/SL-002-annotation-schema.md
  - docs/project/backlog.md
  - docs/superpowers/plans/2026-07-12-annotation-schema.md
owner: null
---

# SL-002 kind 別注釈スキーマと重複シート処理

## 背景と根本原因

注釈は kind ごとの必須値を持たず、同一シートの複数 YAML は表示時に最後の 1 件だけ残る一方、回答 ID は全ファイルから合算される。

## 根拠

`src/sheetlens/annotations/schema.py:19-38`、`src/sheetlens/pipeline.py:75`、`src/sheetlens/pipeline.py:131`。親監査で role は後者だけ、answered は両ファイル分になることを再現済み。

## 受け入れ条件

- [x] kind 別 discriminated union で必須フィールドと許容フィールドを検証する。
- [x] 同一シート注釈を損失なくマージするか、ファイル名付きエラーとして拒否する。
- [x] 未知、廃止、対象不一致の質問 ID を検出する。
- [x] 空の input_source や内容のない回答を回答済みにできない。

## 対象外

注釈入力用 GUI と外部データベース。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-12-annotation-schema.md) に従って進める。

## 完了証拠

- `uv run pytest tests/test_annotations.py tests/test_compile_e2e.py tests/test_check_e2e.py tests/test_markdown.py -q`: 61 passed。
- `uv run pytest -q`: 497 passed、既存 xlsm テスト由来の warning 1件。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
- kind 別必須値・余分な field、同一 sheet の2 YAML、未知／変更／削除／対象不一致 ID、空回答、`(VBA)` event、legacy ID の compile/check 回帰を検証した。
- advisor の設計レビュー、実装レビュー、完了前レビューを実施し、sheet_role target の表示・回答判定と VBA event の照合・表示に関する指摘を反映した。
