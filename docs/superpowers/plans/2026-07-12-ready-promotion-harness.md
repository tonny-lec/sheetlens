# SL-021 ready 昇格ハーネス実装計画

## 目的

`process-project-backlog` の完了後に、まだ `proposed` の課題から ready 条件を満たすものだけを
機械的に検出し、`ready` へ昇格する薄い接続経路を追加する。backlog 処理本体へ昇格判定の実装を
埋め込まず、独立した harness と post-completion skill で接続する。

## 契約

- `scripts/promote_ready_issues.py check`: project-state を検証し、昇格可能な proposed issue ID を
  表示する。ファイルを変更しない。
- `scripts/promote_ready_issues.py promote --ids <ID ...>`: `check` の出力から skill が確認した ID だけを
  明示的に受け取り、同じ条件で判定し、対象だけを `status: ready` に更新し、`render`、`check` を
  この順序で実行する。`in_progress` が残る場合は変更しない。
- 昇格条件は、根本原因・根拠・受け入れ条件・対象外が非空、受け入れ条件がチェックボックス形式、
  `touches` が非空、依存課題がすべて `done` であること。既存 `check_project_state.py` の parser と
  validator を再利用し、ready 判定だけを harness に置く。
- 1回の promote で新たに ready になった課題を実装開始しない。次回の backlog 処理で選択する。
- status 更新、render、check のどこかで失敗した場合は、対象 issue と backlog の元バイト列を復元し、
  部分適用を残さない。
- 実行直前に clean な `main` と no active issue を確認する。昇格後の管理ファイル変更は接続 skill が
  state-only commit として永続化し、clean main に戻す。

## 接続

- 新しい `$promote-ready-project-issues` skill は上記 harness の薄い wrapper とする。
- `process-project-backlog` には、通常完了（候補なし・clean main・check pass）のときにこの skill を
  1回呼ぶ post-completion trigger だけを追加する。判定ロジックや状態更新手順は process skill に複製しない。

## 検証

- harness の dry-run、昇格、依存未完了、空/不正 project-state、active issue 残存のテスト
- process skill と post-completion skill の構造検証
- `uv run pytest -q`
- `uv run ruff check .`
- `uv run python scripts/check_project_state.py check`
- `git diff --check`
