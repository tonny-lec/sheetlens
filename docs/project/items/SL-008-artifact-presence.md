---
id: SL-008
title: グラフ、図形、ピボット等の存在記録
status: done
priority: P1
type: enhancement
milestone: M2
depends_on: []
touches:
  - src/sheetlens/model/ir.py
  - src/sheetlens/reader/artifacts.py
  - src/sheetlens/reader/workbook.py
  - src/sheetlens/renderers/machine.py
  - tests/test_ir.py
  - tests/test_reader.py
  - tests/test_machine.py
owner: null
---

# SL-008 グラフ、図形、ピボット等の存在記録

## 背景と根本原因

charts、drawings、pivots の存在を保持する IR がなく、「存在しない」と「未抽出」を区別できない。

## 根拠

`src/sheetlens/model/ir.py:53-61`、`docs/superpowers/specs/2026-07-07-sheetlens-design.md:198-204`。

## 受け入れ条件

- [x] シート別の artifact type、件数、OOXML part を保存する。
- [x] 詳細未対応は gap として manifest に出す。
- [x] chart、image/shape、pivot part をテストする。

## 対象外

グラフ系列、図形レイアウト、ピボット定義の完全解析。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-11-artifact-presence.md) に従って進める。

## 完了証拠

- `uv run pytest tests/test_ir.py tests/test_reader.py tests/test_machine.py -q`: 24 passed。
- `uv run pytest -q`: 411 passed。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
- 実 openpyxl chart workbook で、シート別の chart 件数と `xl/charts/chart1.xml` を抽出した。
- 独立レビューで非 OOXML namespace/type の末尾一致による誤計上と、予期しない
  scanner 例外の握りつぶしを検出し、公式 Transitional/Strict QName・relationship URI の
  allowlist、unknown namespace gap、unexpected exception 伝播へ修正した。再レビューでは
  回避経路と追加 must-fix は見つからなかった。
- Gap Finder の指摘を受け、壊れた package の継続を装っていた monkeypatch テストを
  scanner 単体契約へ修正し、正常な実 package の `read_workbook` 統合テストを追加した。
- Advisor は計画前と完了前に呼び出したが、どちらも助言本文は空で追加指摘はなかった。
