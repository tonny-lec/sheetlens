---
id: SL-010
title: VML ボタン抽出の XML 解析化
status: ready
priority: P2
type: defect
milestone: M2
depends_on: []
touches:
  - src/sheetlens/model/ir.py
  - src/sheetlens/reader/buttons.py
  - tests/test_vba.py
owner: null
---

# SL-010 VML ボタン抽出の XML 解析化

## 背景と根本原因

VML macro は namespace prefix 固定の正規表現で抽出され、label と欠損 relationship を保持しない。

## 根拠

`src/sheetlens/reader/buttons.py:12`、`:32-43`、`src/sheetlens/model/ir.py:34-37`。

## 受け入れ条件

- [ ] ElementTree で namespace URI により解析し、shape label と macro を対応付ける。
- [ ] 別 prefix、entity、欠損 VML、複数ボタンをテストする。
- [ ] ActiveX は存在または gap を記録する。

## 対象外

ActiveX コントロールの完全なプロパティ解析。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
