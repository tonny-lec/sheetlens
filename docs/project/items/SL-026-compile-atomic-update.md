---
id: SL-026
title: compile のアトミック更新と排他制御
status: proposed
priority: P2
type: defect
milestone: M3
depends_on: [SL-013]
touches:
  - src/sheetlens/pipeline.py
  - src/sheetlens/question_ids.py
  - tests/test_compile_e2e.py
  - tests/test_extract_e2e.py
owner: null
---

# SL-026 compile のアトミック更新と排他制御

## 背景と根本原因

SL-013 で extract の再生成は staging と置換により保護されたが、compile は catalog 保存後に sheet Markdown、README、questions を順番に上書きする。途中の I/O 失敗や同時実行で、異なる世代の成果物が混在する可能性がある。

## 根拠

`src/sheetlens/pipeline.py` の `_write_views()` は複数ファイルを直接更新し、`compile_project()` はその前に `question-ids.json` を保存する。extract 用の lock は compile では取得されない。

## 受け入れ条件

- [ ] catalog、README、questions、全 sheet Markdown を一つの生成世代として staging へ書き、検証後にアトミックに置換する。
- [ ] 途中失敗時に旧生成物と annotations を完全に保持し、catalog だけが先に更新されない。
- [ ] extract と compile、compile 同士の競合を共有 lock で検出・拒否する。
- [ ] write failure、swap failure、rollback、同時実行境界を failure injection と E2E テストで検証する。

## 対象外

分散トランザクション、自動 retry、annotations の自動マージ。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に設計、失敗注入、競合検出、旧成果物保持、全検証コマンドの結果を記録する。
