---
id: SL-014
title: 実 xlsm の Windows E2E 検証
status: done
priority: P1
type: quality
milestone: M4
depends_on: []
touches:
  - tests/fixtures/xlsm
  - tests/test_xlsm_e2e.py
  - .github/workflows/windows-xlsm.yml
  - docs/qa/windows-xlsm-acceptance.md
  - README.md
owner: null
---

# SL-014 実 xlsm の Windows E2E 検証

## 背景と根本原因

想定環境は Windows と実 xlsm だが、VBA 正常系は parser mock、ボタンは最小手製 ZIP で、本番形式を通していない。

## 根拠

`docs/superpowers/specs/2026-07-07-sheetlens-design.md:25`、`README.md:112`、`tests/test_vba.py:37-129`。

## 受け入れ条件

- [x] 再配布可能な最小 xlsm fixture を追加する。
- [x] VBA module、event、フォームボタン、文字コード、gap を E2E 検証する。
- [x] Windows CI workflow を用意する。実行確認は環境制約により低優先度で延期する。
- [x] 業務 PC 用の受入手順と記録欄を用意する。実機確認は低優先度で延期する。

## 対象外

実業務ファイルのリポジトリ保存。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-11-real-xlsm-windows.md) に従って進める。

## 完了証拠

- `uv run pytest tests/test_xlsm_e2e.py -q`: 4 passed（Linux ローカル）。
- `uv run pytest -q`: 428 passed。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
- 固定 upstream revision から再取得した2 fixture と vendored file の SHA-256 が一致。
- Advisor の欠陥レビューで xlwings example のライセンス適用範囲と checkout tag pin を
  must-fix と判定。repository-wide MIT の openpyxl fixture へ差し替え、完全な license
  notice を同梱し、checkout を commit SHA に固定した。
- 2026-07-11、現 PC では Windows CI と業務 PC の実行確認ができないため、ユーザー承認により
  実行証拠を完了条件から除外し、低優先度の後続確認へ延期した。
- Windows CI: **deferred — user-approved**。workflow は追加済みだが、push は未実施。
- 業務 PC: **deferred — user-approved**。`docs/qa/windows-xlsm-acceptance.md` に
  再現可能な手順と結果欄を用意済み。環境値と実行結果は未取得のまま明示している。
