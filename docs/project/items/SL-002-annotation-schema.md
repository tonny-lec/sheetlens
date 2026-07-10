---
id: SL-002
title: kind 別注釈スキーマと重複シート処理
status: proposed
priority: P1
type: defect
milestone: M1
depends_on: [SL-001]
touches:
  - src/sheetlens/annotations/schema.py
  - src/sheetlens/pipeline.py
  - src/sheetlens/renderers/markdown.py
  - tests/test_annotations.py
  - tests/test_compile_e2e.py
owner: null
---

# SL-002 kind 別注釈スキーマと重複シート処理

## 背景と根本原因

注釈は kind ごとの必須値を持たず、同一シートの複数 YAML は表示時に最後の 1 件だけ残る一方、回答 ID は全ファイルから合算される。

## 根拠

`src/sheetlens/annotations/schema.py:19-38`、`src/sheetlens/pipeline.py:75`、`src/sheetlens/pipeline.py:131`。親監査で role は後者だけ、answered は両ファイル分になることを再現済み。

## 受け入れ条件

- [ ] kind 別 discriminated union で必須フィールドと許容フィールドを検証する。
- [ ] 同一シート注釈を損失なくマージするか、ファイル名付きエラーとして拒否する。
- [ ] 未知、廃止、対象不一致の質問 ID を検出する。
- [ ] 空の input_source や内容のない回答を回答済みにできない。

## 対象外

注釈入力用 GUI と外部データベース。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
