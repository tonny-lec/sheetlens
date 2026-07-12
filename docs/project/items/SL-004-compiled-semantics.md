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

意味層の正が Markdown にしかなく、注釈だけでなく Excel 由来のセル値、シート名、ファイル名、質問文、VBA・ボタン名などの外部由来文字列も、出力位置によっては Markdown の文書構造として解釈される。

## 根拠

`src/sheetlens/renderers/markdown.py:39-51` はグリッドセルの改行と pipe だけを処理し、`:184-214`、`:331-343` は注釈・質問・対象名を文脈別に無害化せず挿入する。`raw.json` 以外の AI 向け出力に、外部入力が Markdown の見出し、blockquote、code fence、リンク、HTML として解釈される経路が残っている。

## 受け入れ条件

- [ ] 構造要素 ID と provenance を含む compiled 意味層 JSON を生成する。
- [ ] Markdown は compiled データから生成し、見出し、blockquote、code fence を注釈から生成させない。
- [ ] role、note、value、cell value、sheet name、file name、question text、VBA・button name に改行、`##`、`> ❓`、backtick、pipe、link、HTML を含むテストを追加する。
- [ ] Markdown の出力位置ごとに literal text と構文を分離し、外部入力によって見出し、blockquote、code fence、link、HTML の構造が変化しない。
- [ ] Markdown parser 上の正規見出し集合と構文要素集合が外部入力で変化しない。

## 対象外

一般目的の prompt-injection 検出器。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に検証コマンド、結果、レビュー結果を記録する。
