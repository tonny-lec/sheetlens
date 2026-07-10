---
id: SL-004
title: compiled 意味層 JSON と Markdown 無害化
status: proposed
priority: P1
type: enhancement
milestone: M1
depends_on: [SL-002, SL-003]
touches:
  - src/sheetlens/model/ir.py
  - src/sheetlens/pipeline.py
  - src/sheetlens/renderers/machine.py
  - src/sheetlens/renderers/markdown.py
  - tests/test_machine.py
  - tests/test_markdown.py
  - tests/test_compile_e2e.py
owner: null
---

# SL-004 compiled 意味層 JSON と Markdown 無害化

## 背景と根本原因

意味層の正が Markdown にしかなく、注釈テキスト中の改行や見出しが文書構造として解釈される。

## 根拠

`src/sheetlens/renderers/markdown.py:15-35` と `src/sheetlens/renderers/markdown.py:94-96` は注釈を無加工で挿入し、無害化はグリッドセル `src/sheetlens/renderers/markdown.py:39-40` に限られる。

## 受け入れ条件

- [ ] 構造要素 ID と provenance を含む compiled 意味層 JSON を生成する。
- [ ] Markdown は compiled データから生成し、見出し、blockquote、code fence を注釈から生成させない。
- [ ] role、note、value に改行、`##`、`> ❓`、backtick、pipe を含むテストを追加する。
- [ ] Markdown parser 上の正規見出し集合が注釈内容で変化しない。

## 対象外

一般目的の prompt-injection 検出器。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
