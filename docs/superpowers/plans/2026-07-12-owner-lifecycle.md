# SL-022 owner と status のライフサイクル再設計 実装計画

## 目的

課題状態と owner の組を単一の snapshot invariant として検証し、開始・再開・中断・完了・
再オープン・復旧で owner だけが取り残される不整合を防ぐ。遷移履歴や外部 tracker は追加せず、
親 workflow の契約と validator の現在状態検査を一致させる。

## 調査結果と設計

- `in_progress` は owner が空白でない文字列、`proposed`、`ready`、`blocked`、`done`、
  `cancelled` は owner `null` とする。空文字・空白だけの owner は null と同一視せず、入力エラーとして
  単一診断する。自動 trim はしない。
- `in_progress -> blocked` は status と owner null を同時更新し、理由・解除条件・次の確認を記録する。
  `blocked -> in_progress` は再開主体と scope を確認して、新しい owner と status を同時更新する。
- `done -> ready` は owner null のまま再オープン理由を記録し、その後の着手時だけ owner を付ける。
  統合後検証失敗による例外的な `done -> in_progress` は recovery commit で owner Codex を同時設定する。
- 既存 `in_progress` の再開で owner・branch・worktree の関係が不明、または引き継ぎ根拠がない場合は
  owner を黙って上書きせず停止する。

## 実装順序

1. project README と select/process/finish skills に status/owner 遷移表、親だけが行う atomic update、
   失敗時の修復手順を追加する。
2. `check_project_state.py` の owner 検証を null または非空白文字列へ明確化する。
3. validator の全 status matrix、owner 空白、`blocked -> in_progress` の status-only failure、
   item write 1回後の render -> check 復旧をテストする。
4. proxy metric として修復ケースの item write、render、check、途中状態 check 数を記録する。

## 検証

- 対象テスト: `uv run pytest tests/test_project_state.py -q`
- 必須検証: `uv run pytest -q`、`uv run ruff check .`、`uv run python scripts/check_project_state.py check`、`git diff --check`
- proxy metric: 修復は item write 1、render 1、check 1、途中状態への check 0 とし、snapshot validation
  の品質を落とさない。
