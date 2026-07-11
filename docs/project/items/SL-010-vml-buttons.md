---
id: SL-010
title: VML ボタン抽出の XML 解析化
status: done
priority: P2
type: defect
milestone: M2
depends_on: []
touches:
  - src/sheetlens/reader/buttons.py
  - src/sheetlens/reader/workbook.py
  - tests/test_vba.py
  - tests/test_xlsm_e2e.py
  - docs/project/items/SL-010-vml-buttons.md
  - docs/project/backlog.md
  - docs/superpowers/plans/2026-07-11-vml-buttons.md
owner: null
---

# SL-010 VML ボタン抽出の XML 解析化

## 背景と根本原因

VML macro は namespace prefix 固定の正規表現で抽出され、label と欠損 relationship を保持しない。

## 根拠

`src/sheetlens/reader/buttons.py:12`、`:32-43`、`src/sheetlens/model/ir.py:34-37`。

## 受け入れ条件

- [x] ElementTree で namespace URI により解析し、shape label と macro を対応付ける。
- [x] 別 prefix、entity、欠損 VML、複数ボタンをテストする。
- [x] ActiveX は存在または gap を記録する。

## 対象外

ActiveX コントロールの完全なプロパティ解析。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-11-vml-buttons.md) に従って進める。

## 完了証拠

- `uv run pytest tests/test_vba.py tests/test_xlsm_e2e.py -q`: 14 passed。
- `uv run pytest -q`: 441 passed。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
- 実xlsmでlabel `Button 1`、macro `[0]!Button1_Click`、ActiveX 2件gapを確認した。
- advisor reviewで指摘された重複relationship IDの先勝ちをfail-closedへ修正し、VMLと
  ActiveXの重複ID回帰テストを追加した。他にblocking findingなし。
