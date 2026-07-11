# SL-019 backlog 自動直列処理 skill 実装計画

## 目的

既存の project state、選定 skill、完了 skill を再利用し、一度の明示起動で eligible な課題を
安全に直列処理する instruction-only skill を追加する。

## 設計

- 正本は `docs/project/items/*.md` のまま維持し、skill 独自の状態を持たない。
- 一課題ごとに `検証 -> 選定/再開 -> 着手 -> 情報収集 -> 設計 -> 実装 -> 検証 -> 完了`
  を行う。
- 完了後に clean な `main` と正常な project state を確認できた場合だけ次の課題へ進む。
- 候補なしは正常終了とし、曖昧さ、失敗、承認待ちは停止して再開条件を報告する。
- runtime script、追加 hook、設定、状態ファイルは作らない。

## 実装

1. skill-creator で `.agents/skills/process-project-backlog/` を初期化する。
2. `SKILL.md` を既存 skill の合成 workflow と停止条件に限定する。
3. `agents/openai.yaml` を明示起動専用として生成する。
4. skill validator と隔離した代表ケースで検証する。
5. advisor review 後に全リポジトリ検証を行い、`$finish-project-issue` で統合する。

## 検証

- skill creator の `quick_validate.py`
- 候補なし、active 継続、途中停止の隔離 forward test
- `uv run pytest -q`
- `uv run ruff check .`
- `uv run python scripts/check_project_state.py check`
- `git diff --check`
