# SL-017 パッケージとリポジトリの衛生管理実装計画

## 調査結果

- `pyproject.toml` は readme、license、authors、project URLs、classifiers を定義していない。
- 現在の Hatch sdist はリポジトリ全体を含み、`.agents`、docs、tests、workflow、`uv.lock` まで配布される。
- `.gitignore` は `*.sheetlens/`、生成 Excel、dist/build、coverage の包括的な除外を持たない。
- origin は `https://github.com/tonny-lec/sheetlens.git` で、README の clone URL と一致する。

## 承認記録とライセンス方針

2026-07-12 に advisor へ計画を提示し、ユーザーの明示した「個人利用のためライセンス不要」
という決定を受けて、次を条件付き承認された。

- author は公開名 `tonny-lec`、URLs は確認済み origin を使用する。
- sdist は `README.md`、`pyproject.toml`、`src/**`、生成 `PKG-INFO` に限定する。ただし Hatchling が
  VCS exclusion file として強制同梱する root `.gitignore` は明示的な例外とする。
- package smoke は wheel と sdist の内容・metadata を標準ライブラリで検証する。
- ignore は既存の承認済み `tests/fixtures/xlsm/*.xlsm` を例外化し、README に実業務 Excel の持込禁止を明記する。
- CI は build 前に `dist` を空にし、成果物数を決定的に検証する。

ライセンスについては、ユーザー決定に基づき `LICENSE`、`project.license`、ライセンス classifier を
追加しない。README には「個人利用専用で、再配布・利用許諾を付与していない」と明記し、
`Private :: Do Not Upload` classifier で PyPI 公開対象外を示す。これはライセンスを付与するものではない。

## 実装方針

1. `readme`、author、確認済み GitHub URLs、Python 3.12--3.14 等の classifiers を追加する。
2. Hatch sdist の include を README、pyproject、src に限定する。Hatchling の強制同梱 `.gitignore` と
   `PKG-INFO` 以外を含めない。
3. `scripts/wheel_smoke.py` を wheel の install/CLI に加え、sdist の required/forbidden member と
   built metadata の検証に拡張する。
4. quality workflow を `uv build --sdist --wheel` に変更し、build 前に `dist` を空にして、wheel と
   sdist が各1件であることを smoke が検証する。
5. `.gitignore` に生成 `.sheetlens/`、Excel（承認済み fixture 例外）、dist/build、coverage、cache を追加し、
   README に実業務 Excel を commit・upload しない運用を記載する。

## 変更対象

- `pyproject.toml`
- `.gitignore`
- `README.md`
- `.github/workflows/quality.yml`
- `scripts/wheel_smoke.py`
- `docs/project/items/SL-017-package-repository-hygiene.md`、`docs/project/backlog.md`

## 検証

```text
uv build --sdist --wheel
uv run --frozen python scripts/wheel_smoke.py
uv run pytest -q
uv run ruff check .
uv run python scripts/check_project_state.py check
git diff --check
```
