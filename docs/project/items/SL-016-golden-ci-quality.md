---
id: SL-016
title: golden test と CI 品質ゲート
status: ready
priority: P2
type: quality
milestone: M4
depends_on: []
touches:
  - pyproject.toml
  - .github/workflows
  - tests/golden
  - tests/test_markdown.py
  - tests/test_machine.py
owner: null
---

# SL-016 golden test と CI 品質ゲート

## 背景と根本原因

CI、型チェック、coverage gate がなく、設計書が要求する Markdown golden snapshot に対して現在の Markdown テストは部分文字列だけを検証する。

## 根拠

`pyproject.toml:17-30`、`docs/superpowers/specs/2026-07-07-sheetlens-design.md:187-196`、`tests/test_markdown.py:26-41`。

## 受け入れ条件

- [ ] Ubuntu/Windows と Python 3.12-3.14 の CI を追加する。
- [ ] lock、pytest、Ruff、型、coverage、build、wheel smoke を検証する。
- [ ] 代表 fixture の raw、manifest、Markdown の決定的 golden を追加する。
- [ ] 新規品質依存は事前承認を得る。

## 対象外

すべての Python/OS 組み合わせと100% coverage。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
