---
id: SL-014
title: 実 xlsm の Windows E2E 検証
status: ready
priority: P1
type: quality
milestone: M4
depends_on: []
touches:
  - tests/fixtures
  - tests/test_vba.py
  - tests/test_extract_e2e.py
  - .github/workflows
  - README.md
owner: null
---

# SL-014 実 xlsm の Windows E2E 検証

## 背景と根本原因

想定環境は Windows と実 xlsm だが、VBA 正常系は parser mock、ボタンは最小手製 ZIP で、本番形式を通していない。

## 根拠

`docs/superpowers/specs/2026-07-07-sheetlens-design.md:25`、`README.md:112`、`tests/test_vba.py:37-129`。

## 受け入れ条件

- [ ] 再配布可能な最小 xlsm fixture を追加する。
- [ ] VBA module、event、フォームボタン、文字コード、gap を E2E 検証する。
- [ ] Windows CI で成功する。
- [ ] 業務 PC の受入結果を記録する。

## 対象外

実業務ファイルのリポジトリ保存。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
