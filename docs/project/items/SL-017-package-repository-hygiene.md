---
id: SL-017
title: パッケージとリポジトリの衛生管理
status: ready
priority: P3
type: quality
milestone: M4
depends_on: []
touches:
  - pyproject.toml
  - .gitignore
  - README.md
owner: null
---

# SL-017 パッケージとリポジトリの衛生管理

## 背景と根本原因

配布メタデータと sdist 境界が不十分で、生成 xlsx、`.sheetlens/`、build、coverage 成果物の ignore が不足する。

## 根拠

`pyproject.toml:1-25`、`.gitignore:1-4`、`README.md:92-95`。

## 受け入れ条件

- [ ] readme、license、authors、URLs、classifiers を定義する。
- [ ] sdist include/exclude と wheel smoke を検証する。
- [ ] 生成 Excel、`*.sheetlens/`、dist、build、coverage を ignore し、実業務 Excel の持込禁止を文書化する。

## 対象外

PyPI 公開とリリース自動化。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
