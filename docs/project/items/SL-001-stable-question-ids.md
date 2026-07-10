---
id: SL-001
title: 質問 ID の安定化と旧 ID 移行
status: ready
priority: P1
type: defect
milestone: M1
depends_on: []
touches:
  - src/sheetlens/detectors/questions.py
  - src/sheetlens/annotations/schema.py
  - src/sheetlens/pipeline.py
  - tests/test_questions.py
  - tests/test_compile_e2e.py
owner: null
---

# SL-001 質問 ID の安定化と旧 ID 移行

## 背景と根本原因

質問 ID が意味ではなく走査順の連番であり、前方へ質問が追加されると既存回答が別質問へ対応する。

## 根拠

`src/sheetlens/detectors/questions.py:39-40`、`src/sheetlens/pipeline.py:131`。親監査で同じ Input シートの役割質問が `q-001` から `q-003` へ変化することを再現済み。

## 受け入れ条件

- [ ] `sheet/category/target` の正規化値から決定的な ID または fingerprint を生成する。
- [ ] 前方へシート、非表示属性、入力規則を追加しても既存質問 ID が変化しない。
- [ ] 旧連番 ID の移行または stale 警告を提供する。
- [ ] 削除・内容変更された質問 ID を `check` が報告する。

## 対象外

質問文の全面的な文言変更と新しい質問カテゴリの追加。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
