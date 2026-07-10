# SheetLens 次課題選定 skill 設計書

## 目的

SheetLens の改善作業を開始または再開するとき、リポジトリ内の課題管理状態から、現在優先して
対応すべき課題を 1 件だけ読み取り専用で返すリポジトリ専用 skill を作成する。

基本運用は一人での直列開発とする。未完了の `in_progress` 課題がある間は新しい課題を選ばず、
現在の課題を完了してから次の `ready` 課題へ移る。

## 配置と構成

skill 名は `select-next-project-issue` とし、次の構成で配置する。

```text
.agents/skills/select-next-project-issue/
├── SKILL.md
└── agents/
    └── openai.yaml
```

- `SKILL.md`: 発火条件、選定手順、エラー処理、返却形式を定義する。
- `agents/openai.yaml`: skill 一覧向けの表示名、短い説明、既定プロンプトを定義する。
- 新しい選定スクリプトは追加しない。既存の `scripts/check_project_state.py` と生成済み
  `docs/project/backlog.md` を再利用し、選定規則を二重実装しない。
- 課題状態、owner、受け入れ条件、`backlog.md` は変更しない。

## 選定フロー

1. repository root で `uv run python scripts/check_project_state.py check` を実行する。
2. `check` が成功した場合だけ、同期済みの `docs/project/backlog.md` を読む。
3. `status=in_progress` の課題数で分岐する。
   - 1 件: その課題を「継続」として返す。新しい候補は選ばない。
   - 2 件以上: 直列開発の前提と矛盾するため、課題を 1 件に決めず全 ID を示して停止する。
   - 0 件: `uv run python scripts/check_project_state.py next` を実行する。
4. `next` が成功した場合だけ、`^P[0-3] SL-[0-9]{3} ` に一致する最初の候補を「新規着手」
   として選ぶ。既存 CLI の優先度、マイルストーン、ID 順をそのまま採用する。
5. 選定した ID に一致する `docs/project/items/SL-NNN-*.md` を読み、正本の情報を返す。

`in_progress` がない場合、現在実行中の課題との `touches` 競合も存在しない。そのため、
単独・直列運用では競合有無を追加のソートキーにしない。

## 返却形式

正常時は次の順序で簡潔に返す。

```text
判定: 継続 | 新規着手
課題: SL-NNN 課題名
優先度: P0 | P1 | P2 | P3
状態: in_progress | ready
マイルストーン: M1 | M2 | M3 | M4
正本: docs/project/items/SL-NNN-*.md
理由: 現在進行中の課題、または next の最上位候補
```

skill は選定結果を報告するだけとする。`ready` を `in_progress` に変更したり owner を設定したり
せず、状態更新は親エージェントの別工程に残す。

## エラーと境界条件

- `check` が終了コード 1 または 2 を返した場合は、候補を推測せず検証エラーを報告する。
- `next` が終了コード 1 または 2 を返した場合は、stdout の先頭行を候補として扱わない。
- `next` が終了コード 0 かつ候補行がない場合は「着手可能な課題なし」と返す。
- `in_progress` が複数ある場合は優先順位で 1 件に丸めず、直列運用との不整合として報告する。
- 選定 ID に一致する正本ファイルを一意に解決できない場合は、管理状態の不整合として停止する。

## テスト方針

skill は `superpowers:writing-skills` の RED-GREEN-REFACTOR に従って作成する。

skill なしのベースラインと skill 適用後で、最低限次の読み取り専用シナリオを比較する。

1. `in_progress` 1 件と、より高優先度の `ready` がある場合に、進行中課題を返す。
2. `in_progress` がなく複数の `ready` がある場合に、`next` の先頭候補を返す。
3. `in_progress` が複数ある場合に、任意の 1 件を選ばず不整合を報告する。
4. 管理状態が不正な場合に、候補を推測しない。
5. 着手可能候補がない場合に、その旨を返す。

実装後は次を実行する。

```bash
python /home/tonny/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .agents/skills/select-next-project-issue
uv run python scripts/check_project_state.py check
uv run python scripts/check_project_state.py next
uv run pytest tests/test_project_state.py -q
uv run ruff check .
```

さらに、新しいコンテキストのサブエージェントに skill を使わせ、返却形式と選定結果を
forward-test する。

## 対象外

- 課題の状態遷移、owner 設定、backlog 再生成
- 複数課題の並行割り当て
- 既存 `next` コマンドの選定順変更
- GitHub Issues や外部課題管理サービスとの同期
