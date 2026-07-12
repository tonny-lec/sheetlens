---
id: SL-020
title: 課題完了状態の権限と中断復旧
status: done
priority: P1
type: quality
milestone: M4
depends_on: []
touches:
  - .agents/skills/finish-project-issue/SKILL.md
  - .agents/skills/process-project-backlog/SKILL.md
  - .codex/hooks/stop_git_completion.py
  - tests/test_git_completion_hook.py
  - docs/project/README.md
  - docs/project/items/SL-020-completion-state-authority.md
  - docs/project/backlog.md
  - docs/superpowers/plans/2026-07-12-completion-state-authority.md
owner: null
---

# SL-020 課題完了状態の権限と中断復旧

## 背景と根本原因

今回の実証では、レートリミットにより `finish-project-issue` を利用できない状況で、
Codex 自身の判断により課題が `done` へ変更された。その結果、commit・main への統合・
統合後検証が完了していない `done` 課題が作業ツリーに残った。`done` は検証結果だけでなく、
完了ワークフローの実行権限と中断時の復旧規則まで含めて定義する必要がある。

## 根拠

`.agents/skills/finish-project-issue/SKILL.md` の status 更新手順、
`.codex/hooks/stop_git_completion.py` の完了宣言ゲート、今回の SL-013 の中断状態。

## 受け入れ条件

- [x] `done` に遷移できる主体、必要な finish skill の実行結果、commit・local main 統合・統合後検証の完了条件を明文化する。
- [x] finish skill が利用できない、または途中で中断した場合に、Codex が独断で `done` にせず、`in_progress` または `blocked` と理由・再開条件を保持する。
- [x] `done` だが必要な Git 完了状態に達していない既存状態を、変更範囲を確認したうえで安全に復旧する最小ケースをテストする。
- [x] 既存の検証品質を下げず、重複した検証・長大な出力・不要なツール往復を減らせるかを、ツール呼び出し数・重複実行数・出力サイズなど取得可能な代理指標で比較する。
- [x] 最も重要な不確実性を「finish skill 利用不能時の状態遷移」と明示し、それだけを検証する最小の中断・再開ケースを定義する。

## 対象外

`.git` が read-only になる原因の解決、ユーザー所有の config の扱い、remote 操作、
複数課題の同時完了。

## 実装計画

[実装計画](../../superpowers/plans/2026-07-12-completion-state-authority.md) に従って進める。

## 完了証拠

- `uv run pytest tests/test_git_completion_hook.py -q`: 8 passed。
- `uv run pytest -q`: 500 passed、既存 xlsm テスト由来の warning 1件。
- `uv run ruff check .`: PASS。
- `uv run python scripts/check_project_state.py check`: PASS。
- `git diff --check`: PASS。
- `done` の provisional/authoritative 区別、親 finish workflow の権限、`in_progress`（owner Codex）／
  `blocked`（owner null）への中断復旧、統合後検証失敗の state-only recovery、branch cleanup 失敗時の
  done 維持を README と skills に明文化した。
- clean task branch の provisional `done` を Stop hook が拒否するケース、未統合 `feat/SL-*` branch を
  別課題選択前に fast-forward する forward case を検証した。
- proxy metric は、非 main の早期停止が従来基準4 subprocessから2へ減少、healthy checker は4 unique
  subprocess、重複0、stdout/stderr は rev-parse の root 行と branch の main 行だけであることを測定した。
- advisor のレビューで指摘された blocked owner 契約、forward recovery、全 output byte 計測、未コミット
  provisional done の具体的復旧手順を反映した。
