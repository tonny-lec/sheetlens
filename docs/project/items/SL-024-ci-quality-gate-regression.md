---
id: SL-024
title: CI 品質ゲート回帰の修復
status: proposed
priority: P1
type: defect
milestone: M4
depends_on: [SL-016]
touches:
  - src/sheetlens/cli.py
  - src/sheetlens/pipeline.py
  - src/sheetlens/renderers/markdown.py
  - tests/test_cli.py
  - tests/test_compile_e2e.py
  - tests/test_markdown.py
  - tests
owner: null
---

# SL-024 CI 品質ゲート回帰の修復

## 背景と根本原因

現行 `main` は通常の pytest と Ruff は通過するが、CI が必須化している `mypy` と実効 coverage gate を通過しない。型エラーを未解決のまま残し、coverage の表示値が 90% に丸められているため、ローカル確認だけでは回帰を見落としやすい。

## 根拠

`.github/workflows/quality.yml` は `mypy src` と `--cov-fail-under=90` を実行する。現状の実測は `mypy` 14 errors、coverage 89.87% であり、pytest 504 passed でも CI 条件を満たさない。

## 受け入れ条件

- [ ] `uv run --frozen mypy src` の14件の型エラーを、包括的な ignore や型エラーの握りつぶしを使わず解消する。
- [ ] `uv run --frozen pytest --cov=src/sheetlens --cov-report=term-missing --cov-fail-under=90` が実効 coverage 90%以上で成功する。
- [ ] CI workflow に記載された lock、pytest、Ruff、mypy、coverage、build、wheel smoke の各コマンドが成功する。
- [ ] 型修正と coverage 補完が、既存の意味保持・エラー処理・決定性を壊さないことを回帰テストで確認する。

## 対象外

coverage 閾値の引き下げ、包括的な `type: ignore` の追加、品質ゲート自体の無効化。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に CI 相当コマンド、実測 coverage、型チェック結果、レビュー結果を記録する。
