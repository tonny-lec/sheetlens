---
id: SL-017
title: パッケージとリポジトリの衛生管理
status: done
priority: P3
type: quality
milestone: M4
depends_on: []
touches:
  - pyproject.toml
  - .gitignore
  - README.md
  - .github/workflows/quality.yml
  - scripts/wheel_smoke.py
  - docs/superpowers/plans/2026-07-12-package-repository-hygiene.md
  - docs/project/items/SL-017-package-repository-hygiene.md
  - docs/project/backlog.md
owner: null
---

# SL-017 パッケージとリポジトリの衛生管理

## 背景と根本原因

配布メタデータと sdist 境界が不十分で、生成 xlsx、`.sheetlens/`、build、coverage 成果物の ignore が不足する。

## 根拠

`pyproject.toml:1-25`、`.gitignore:1-4`、`README.md:92-95`。

## 受け入れ条件

- [x] readme、authors、URLs、classifiers を定義し、個人利用のため再配布・利用許諾を付与しないことを明記する（license metadata は追加しない）。
- [x] sdist include/exclude と wheel smoke を検証する。
- [x] 生成 Excel、`*.sheetlens/`、dist、build、coverage を ignore し、実業務 Excel の持込禁止を文書化する。

## 対象外

PyPI 公開とリリース自動化。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-12-package-repository-hygiene.md) に従って進める。

## 完了証拠

advisor は、ユーザー決定に基づき `LICENSE`、`project.license`、ライセンス classifier を追加せず、
README に個人利用専用・再配布禁止を明記し、`Private :: Do Not Upload` を付与する方針を承認した。
- `pyproject.toml`: readme、author、確認済み GitHub URLs、Python 3.12--3.14 classifiers、
  sdist allowlist を追加。license metadata は追加していない。
- `.gitignore`: `*.sheetlens/`、生成 Excel、dist/build、coverage、cache を追加し、承認済み静的
  XLSM fixture を例外化。
- `git check-ignore`: 生成 Excel、`*.sheetlens/`、dist、build、coverage、pytest/Ruff cache は除外。
  `tests/fixtures/xlsm/openpyxl-vba-test.xlsm` は例外として除外されないことを確認。
- `README.md`: 個人利用専用、再配布・アップロード禁止、実業務 Excel 持込禁止、配布境界を記載。
- package smoke: `uv build --sdist --wheel` 後、sdist allowlist（`.gitignore`、README、pyproject、
  `src/**`、`PKG-INFO`）と forbidden payload、wheel install、metadata、CLI `--help` を PASS。
- `uv run pytest -q`: 468 passed。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
