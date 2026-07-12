# SL-020 課題完了状態の権限と中断復旧 実装計画

## 目的

`done` を単なる検証済みフラグではなく、finish workflow が local `main` まで完了した
ことの結果として扱う。途中状態を誤って完了宣言せず、task branch や統合後検証失敗から
安全に再開できる契約を、プロジェクト文書・skills・Stop hook・テストで固定する。

## 調査結果と設計

- `done` には task branch 上の provisional state と、commit・`main` への fast-forward・
  `main` 上の必須検証・clean worktree・active issue なしを満たした authoritative state が
  ある。Stop hook は後者の Git/project-state 条件までを機械検査し、finish skill 実行そのものを
  証明するとは記載しない。
- finish 前半で失敗した場合、authoritative な project state は `in_progress` のまま維持する。
  外部 permission や検証失敗で継続不能なら owner を `null` に解放し、blocker の理由・解除条件・
  次の確認を記録して `blocked` にする。独断で `done` にしない。
- task branch に provisional `done` の commit が残った場合、process skill は未統合の
  `feat/SL-*` branch を検出して再開し、別の issue を選ばない。
- fast-forward 後の main 検証失敗は reset/rebase/force をせず、main 上で status を
  `in_progress`（owner は `Codex`）または `blocked`（owner は `null`）へ戻し、理由を記載する
  state-only recovery commit を作る。branch cleanup だけの失敗は done を取り消さず、残存 branch
  を報告する。

## 実装順序

1. `docs/project/README.md` に authoritative/provisional done と復旧状態の状態遷移表を追加する。
2. process/finish skill に未統合 branch の再開ゲート、finish 中断、統合後検証失敗、branch cleanup
   失敗の契約を追加する。
3. Stop hook の非 main メッセージを provisional done と再開条件が分かる内容へ更新する。
4. hook tests に clean task branch の provisional done 拒否、未統合 branch の forward-merge が
   selection より先になる最小ケース、checker の command count／重複数／全 output byte の proxy
   metric を追加する。

## 検証

- 対象テスト: `uv run pytest tests/test_git_completion_hook.py -q`
- 必須検証: `uv run pytest -q`、`uv run ruff check .`、`uv run python scripts/check_project_state.py check`、`git diff --check`
- proxy metric: branch/dirty の早期停止と healthy checker の subprocess 呼び出し数、重複 command 数、
  stdout/stderr byte 数を変更前基準と比較し、必須の統合前後検証は削減しない。
