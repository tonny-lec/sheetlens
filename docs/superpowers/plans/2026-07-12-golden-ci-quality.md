# SL-016 golden test と CI 品質ゲート実装計画

## 目的

固定された代表 XLSM fixture の抽出成果物を raw、manifest、Markdown の golden として
検証し、Ubuntu/Windows × Python 3.12--3.14 で lock、テスト、静的検査、型検査、coverage、
wheel build、wheel smoke を再現可能に実行する。

## 調査結果

- `pyproject.toml` の開発依存は `pytest` と `ruff` のみで、型検査と coverage の設定はない。
- `.github/workflows/windows-xlsm.yml` は実 XLSM E2E 専用で、一般品質ゲートの workflow はない。
- `tests/fixtures/xlsm/openpyxl-vba-test.xlsm` は固定 SHA-256 を検証済みの実 fixture で、VBA、
  ボタン、複数シート、既知の extraction gap を含むため、追加バイナリなしで代表 fixture にできる。
- `read_workbook()` は `source_file` をファイル名、`sha256` を入力バイト列から設定するため、
  fixture と出力ファイル名を固定すれば raw の golden は作業ディレクトリに依存しない。

## 承認ゲート

受入条件の「新規品質依存は事前承認」に従い、2026-07-12 に advisor の承認を得た。

- 開発依存に `mypy` と `pytest-cov` を追加し、`uv.lock` を更新する。
- coverage 閾値は全468テストで実測 90% だったため、`--cov-fail-under=90` に固定する。推測値や 100% は採用しない。

承認条件は、coverage 閾値を実測値の整数切り捨てを下限として測定コマンドとともに完了証拠へ記録すること、
`mypy` の内部エラーを抑制せず、第三者 stub 不足への設定だけを理由付きで許可すること、
型エラー修正が大規模な本体変更へ広がる場合は再度 advisor の範囲承認を得ること、今回の承認対象外の
追加依存を導入しないことである。

## 設計

### CI

- `.github/workflows/quality.yml` に `ubuntu-latest` と `windows-latest`、Python `3.12`--`3.14`
  の 6 ジョブ matrix を追加する。
- 全 matrix ジョブで checkout、uv setup、`uv lock --check`、`uv sync --locked`、
  `uv run --frozen pytest -q` を実行する。
- 代表 Ubuntu ジョブで Ruff、`mypy src`、coverage gate、`uv build --wheel`、
  `scripts/wheel_smoke.py` を実行する。品質ゲートを一つに集約しても、matrix 全体の基本テストと
  lock 検証は維持する。
- 既存 workflow と同じく action は固定 SHA を使い、権限は `contents: read` に限定する。

### Golden

- `tests/golden/test_deterministic_outputs.py` が固定 XLSM を `tmp_path` に抽出し、期待ファイルを
  CRLF から LF へ正規化した UTF-8 bytes の完全一致を検証する。Windows の checkout 設定に依存しない。
- `tests/golden/expected/` に `structure/raw.json`、`manifest.json`、`README.md`、各 sheet の
  Markdown、`questions.md` を保存する。
- 同じ入力を同じ一時 project に再抽出し、対象成果物が初回と一致することも検証する。
- 期待値の更新はテストが自動生成せず、fixture や renderer の意図的な変更時にレビュー付きで行う。

### Wheel smoke

- `scripts/wheel_smoke.py` は標準ライブラリの `venv` と subprocess だけで一時環境を作り、生成 wheel を
  `pip install` して `sheetlens` の import と CLI entry point の起動を検証する。
- wheel smoke 自体の依存解決は pip に任せ、リポジトリの runtime dependency を品質依存へ重複登録しない。

## 変更対象

- `pyproject.toml`: `mypy`、`pytest-cov`、型/coverage 設定
- `.gitignore`: coverage 実行データの除外
- `uv.lock`: lock 更新
- `.github/workflows/quality.yml`: 6 ジョブ matrix と品質ゲート
- `scripts/wheel_smoke.py`: wheel の一時環境 smoke
- `tests/golden/test_deterministic_outputs.py` と `tests/golden/expected/*`: golden
- `docs/project/items/SL-016-golden-ci-quality.md`、`docs/project/backlog.md`: 状態と証拠

## 検証

承認後、実装前後と main 統合後に次を実行する。

```text
uv lock --check
uv run pytest -q
uv run ruff check .
uv run mypy src
uv run pytest --cov=src/sheetlens --cov-report=term-missing --cov-fail-under=90
uv build --wheel
uv run python scripts/wheel_smoke.py
uv run python scripts/check_project_state.py check
git diff --check
```

受入条件の各項目に実行結果を対応付けてから `$finish-project-issue` を起動する。
