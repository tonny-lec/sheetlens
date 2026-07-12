---
id: SL-016
title: golden test と CI 品質ゲート
status: done
priority: P2
type: quality
milestone: M4
depends_on: []
touches:
  - .gitignore
  - docs/project/items/SL-016-golden-ci-quality.md
  - docs/project/backlog.md
  - docs/superpowers/plans/2026-07-12-golden-ci-quality.md
  - pyproject.toml
  - uv.lock
  - .github/workflows/quality.yml
  - scripts/wheel_smoke.py
  - src/sheetlens/detectors/formula_patterns.py
  - src/sheetlens/model/ir.py
  - src/sheetlens/question_ids.py
  - src/sheetlens/reader/artifacts.py
  - src/sheetlens/reader/workbook.py
  - tests/golden/test_deterministic_outputs.py
  - tests/golden/expected
owner: null
---

# SL-016 golden test と CI 品質ゲート

## 背景と根本原因

CI、型チェック、coverage gate がなく、設計書が要求する Markdown golden snapshot に対して現在の Markdown テストは部分文字列だけを検証する。

## 根拠

`pyproject.toml:17-30`、`docs/superpowers/specs/2026-07-07-sheetlens-design.md:187-196`、`tests/test_markdown.py:26-41`。

## 受け入れ条件

- [x] Ubuntu/Windows と Python 3.12-3.14 の CI を追加する。
- [x] lock、pytest、Ruff、型、coverage、build、wheel smoke を検証する。
- [x] 代表 fixture の raw、manifest、Markdown の決定的 golden を追加する。
- [x] 新規品質依存は事前承認を得る。

## 対象外

すべての Python/OS 組み合わせと100% coverage。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-12-golden-ci-quality.md) に従って進める。

## 完了証拠

- advisor 承認（2026-07-12）: `mypy`、`pytest-cov`、`uv.lock` 更新、実測 coverage 閾値 90% を承認。
  今回の承認対象外の依存追加は禁止、`mypy` の包括的抑制は禁止、型修正が大規模化する場合は再承認とした。
- `uv lock --check`: PASS。
- `uv run --frozen pytest --cov=src/sheetlens --cov-report=term-missing --cov-fail-under=90`: 468 passed、90.48%。
- `uv run --frozen ruff check .`: PASS。
- `uv run --frozen mypy src`: PASS（23 source files）。
- `uv build --wheel`: `dist/sheetlens-0.1.0-py3-none-any.whl` を生成。
- `uv run --frozen python scripts/wheel_smoke.py`: PASS（wheel install、import、CLI `--help`）。
- golden test: 代表 XLSM の raw、manifest、README、questions、sheet Markdown の LF 正規化後の一致と再抽出 byte 一致を検証。
- `actionlint`: 環境に未導入のため未実施。代替として quality workflow の PyYAML parse は PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
