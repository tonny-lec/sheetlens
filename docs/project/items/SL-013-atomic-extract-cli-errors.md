---
id: SL-013
title: アトミック再抽出と CLI エラー統一
status: done
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
  - docs/project/items/SL-013-atomic-extract-cli-errors.md
  - docs/project/backlog.md
  - docs/superpowers/plans/2026-07-11-atomic-extract-cli-errors.md
owner: null
---

# SL-013 アトミック再抽出と CLI エラー統一

## 背景と根本原因

extract は旧 structure を先に削除して複数ファイルを順次書き、compile/check は壊れた raw JSON や I/O 例外を統一した利用者向けエラーへ変換しない。

## 根拠

`src/sheetlens/pipeline.py:99-122`、`src/sheetlens/cli.py:39-43`、`:56-65`。

## 受け入れ条件

- [x] 一時ディレクトリへ全成果物を生成・検証後に置換する。
- [x] 途中失敗時に旧成果物と annotations を保持する。
- [x] JSON、Pydantic、Unicode、OSError をパスと復旧方法付きエラーに変換する。

## 対象外

長時間処理の分散トランザクションと自動 retry。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-11-atomic-extract-cli-errors.md) に従って進める。

## 完了証拠

- `uv run pytest tests/test_extract_e2e.py tests/test_compile_e2e.py tests/test_check_e2e.py
  tests/test_cli.py -q`: 44 passed。
- `uv run pytest -q`: 466 passed。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
- stage write/validation、1回目/2回目rename、rollback失敗、post-commit cleanup、new project
  rename、stale stage/lock、managed symlinkをfailure injectionし、旧projectとannotationsを検証した。
- 設計advisor reviewのatomicity/rollback/lock/symlink指摘を反映した。完了前reviewは2回とも
  advisorのChatGPT認証エラーで利用不能だったため、全466テストとself-reviewを最終根拠とした。
