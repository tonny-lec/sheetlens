---
id: SL-003
title: 構造要素への型付き安定 ID 導入
status: ready
priority: P1
type: refactor
milestone: M1
depends_on: [SL-001, SL-002]
touches:
  - src/sheetlens/model/ir.py
  - src/sheetlens/detectors/regions.py
  - src/sheetlens/detectors/formula_patterns.py
  - src/sheetlens/detectors/questions.py
  - src/sheetlens/annotations/schema.py
  - src/sheetlens/pipeline.py
  - src/sheetlens/renderers/markdown.py
owner: null
---

# SL-003 構造要素への型付き安定 ID 導入

## 背景と根本原因

range 文字列だけでは数式パターン、例外式、VBA イベントへ意味注釈を安定して接続できず、Excel 更新後の同一性も表現できない。

## 根拠

`src/sheetlens/pipeline.py:46-63` は range、入力規則、条件付き書式、macro だけを接続キーとし、`src/sheetlens/renderers/markdown.py:125-131` は数式注釈を描画しない。`src/sheetlens/detectors/questions.py:70-73` の VBA 質問は架空シート `(VBA)` に属する。

## 受け入れ条件

- [ ] region、formula-pattern、formula-exception、button、VBA-event に型付き安定 ID を付ける。
- [ ] 注釈は element ID を参照し、存在しない ID を孤立として報告する。
- [ ] 数式パターン、例外式、VBA イベントの回答を該当要素へ織り込む。
- [ ] 既存 range 注釈の移行方法を定義しテストする。

## 対象外

Excel オブジェクト全種類の完全な意味モデル。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
