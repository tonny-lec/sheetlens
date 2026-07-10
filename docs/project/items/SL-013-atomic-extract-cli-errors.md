---
id: SL-013
title: アトミック再抽出と CLI エラー統一
status: ready
priority: P2
type: refactor
milestone: M3
depends_on: []
touches:
  - src/sheetlens/pipeline.py
  - src/sheetlens/cli.py
  - tests/test_extract_e2e.py
  - tests/test_compile_e2e.py
  - tests/test_check_e2e.py
  - tests/test_cli.py
owner: null
---

# SL-013 アトミック再抽出と CLI エラー統一

## 背景と根本原因

extract は旧 structure を先に削除して複数ファイルを順次書き、compile/check は壊れた raw JSON や I/O 例外を統一した利用者向けエラーへ変換しない。

## 根拠

`src/sheetlens/pipeline.py:99-122`、`src/sheetlens/cli.py:39-43`、`:56-65`。

## 受け入れ条件

- [ ] 一時ディレクトリへ全成果物を生成・検証後に置換する。
- [ ] 途中失敗時に旧成果物と annotations を保持する。
- [ ] JSON、Pydantic、Unicode、OSError をパスと復旧方法付きエラーに変換する。

## 対象外

長時間処理の分散トランザクションと自動 retry。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
