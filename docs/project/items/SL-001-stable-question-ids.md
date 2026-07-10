---
id: SL-001
title: 質問 ID の安定化と旧 ID 移行
status: done
priority: P1
type: defect
milestone: M1
depends_on: []
touches:
  - README.md
  - src/sheetlens/detectors/questions.py
  - src/sheetlens/question_ids.py
  - src/sheetlens/pipeline.py
  - src/sheetlens/cli.py
  - src/sheetlens/renderers/markdown.py
  - tests/test_questions.py
  - tests/test_question_ids.py
  - tests/test_extract_e2e.py
  - tests/test_compile_e2e.py
  - tests/test_check_e2e.py
  - tests/test_markdown.py
owner: null
---

# SL-001 質問 ID の安定化と旧 ID 移行

## 背景と根本原因

質問 ID が意味ではなく走査順の連番であり、前方へ質問が追加されると既存回答が別質問へ対応する。

## 根拠

`src/sheetlens/detectors/questions.py:39-40`、`src/sheetlens/pipeline.py:131`。親監査で同じ Input シートの役割質問が `q-001` から `q-003` へ変化することを再現済み。

## 受け入れ条件

- [x] 正規化した `rule/sheet/category/target/text` から決定的な ID と fingerprint を生成する。
- [x] 前方へシート、非表示属性、入力規則を追加しても既存質問 ID が変化しない。
- [x] 旧連番 ID を、annotation YAML の bytes を変更せず catalog 経由で自動解決する。
- [x] 一度確定した legacy alias を後続の再抽出で別質問へ付け替えない。
- [x] 削除・内容変更された質問 ID を `check` が報告する。
- [x] `check` は質問 ID catalog を作成・更新しない。

## 対象外

質問文の全面的な文言変更と新しい質問カテゴリの追加。

## 実装計画

設計は
[`2026-07-10-stable-question-ids-design.md`](../../superpowers/specs/2026-07-10-stable-question-ids-design.md)
に記録した。実装は
[`2026-07-10-stable-question-ids.md`](../../superpowers/plans/2026-07-10-stable-question-ids.md)
に従う。

## 完了証拠

- focused: `uv run pytest tests/test_questions.py tests/test_question_ids.py tests/test_extract_e2e.py tests/test_compile_e2e.py tests/test_check_e2e.py tests/test_markdown.py -q` — `87 passed in 0.99s`
- full: `uv run pytest -q` — `352 passed in 1.63s`
- lint: `uv run ruff check .` — `All checks passed!`
- project state: `uv run python scripts/check_project_state.py check` — exit 0
- final whole-branch review: `Ready to merge: Yes`、Critical / Important / Minor すべてなし
