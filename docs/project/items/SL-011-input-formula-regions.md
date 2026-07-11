---
id: SL-011
title: 手入力列と数式列を分離した質問生成
status: done
priority: P1
type: defect
milestone: M3
depends_on: []
touches:
  - src/sheetlens/detectors/regions.py
  - src/sheetlens/detectors/questions.py
  - tests/test_regions.py
  - tests/test_questions.py
  - tests/test_check_e2e.py
owner: null
---

# SL-011 手入力列と数式列を分離した質問生成

## 背景と根本原因

region 内に数式が 1 セルでもあると領域全体の input_source 質問を生成しない。

## 根拠

`src/sheetlens/detectors/questions.py:21-29`、`:52-56`、`src/sheetlens/detectors/regions.py:23-32`。

## 受け入れ条件

- [x] 手入力セルと数式セルを列または連結範囲で分離する。
- [x] A:B 手入力、C 数式の表では A:B だけを質問対象にする。
- [x] 離れた表と header を誤結合しない。

## 対象外

AI による入力元の自動推定。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-11-input-formula-regions.md) に従って進める。

## 完了証拠

- `uv run pytest tests/test_regions.py tests/test_questions.py tests/test_check_e2e.py::test_check_rejects_pre_split_input_catalog_without_silently_losing_answer -q`: 19 passed。
- `uv run pytest -q`: 419 passed。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
- 数式なし region は従来 target を維持し、数式あり region は純手入力列帯と
  混在列内の手入力連続行へ分離する。数式のみの region では空列を入力と推測しない。
- Advisor レビューで、header 注記が空のデータ列を橋渡しする反例を検出した。
  データ列帯と header-only 列帯を分ける修正と回帰テストを追加した。
- target 分割前の質問 ID を持つ既存カタログは、`check` が `current_ids differ` を伴う
  明示的な質問 ID エラーで停止し、既存回答を黙って未回答化しないことを E2E で確認した。
