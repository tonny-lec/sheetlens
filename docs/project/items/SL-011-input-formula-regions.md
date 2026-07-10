---
id: SL-011
title: 手入力列と数式列を分離した質問生成
status: ready
priority: P1
type: defect
milestone: M3
depends_on: []
touches:
  - src/sheetlens/detectors/regions.py
  - src/sheetlens/detectors/questions.py
  - tests/test_regions.py
  - tests/test_questions.py
owner: null
---

# SL-011 手入力列と数式列を分離した質問生成

## 背景と根本原因

region 内に数式が 1 セルでもあると領域全体の input_source 質問を生成しない。

## 根拠

`src/sheetlens/detectors/questions.py:21-29`、`:52-56`、`src/sheetlens/detectors/regions.py:23-32`。

## 受け入れ条件

- [ ] 手入力セルと数式セルを列または連結範囲で分離する。
- [ ] A:B 手入力、C 数式の表では A:B だけを質問対象にする。
- [ ] 離れた表と header を誤結合しない。

## 対象外

AI による入力元の自動推定。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
