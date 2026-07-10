# SheetLens 改善プロジェクト管理 設計書

## 目的

SheetLens のリファクタリング、欠陥修正、機能強化、品質基盤整備を、本人と Codex が
リポジトリ内だけで継続管理できるようにする。

管理方式は次を満たすことを目的とする。

- Markdown を人間と AI エージェントが読む正本にする。
- 課題の状態、依存関係、完了条件をスクリプトで検証する。
- 依存せず変更範囲も競合しない課題は、サブエージェントで並行実行できるようにする。
- 調査時の根拠、実装時の判断、完了時の検証証拠を同じ課題へ蓄積する。
- GitHub Issues や GitHub Projects を日常運用の必須要素にしない。

## 設計上の決定

### 正本

`docs/project/items/*.md` の課題別 Markdown を唯一の正本とする。状態、優先度、依存関係、
担当、変更予定範囲は課題ファイルの YAML front matter に保存する。

`docs/project/backlog.md` は課題ファイルから生成する一覧であり、手動編集しない。JSON や
YAML の別台帳は作らず、同じ状態を複数箇所で管理しない。

既存文書の役割は変更しない。

- `docs/superpowers/specs/2026-07-07-sheetlens-design.md`: 製品仕様
- `docs/superpowers/plans/2026-07-07-sheetlens-v1.md`: v1 実装履歴
- `docs/project/`: v1 後の継続的な改善プロジェクト管理

### 利用者と実行主体

主な利用者は本人と Codex とする。Codex の親ワーカーが課題選択、状態更新、並行可否判定、
結果統合、完了判定を担当する。サブエージェントは割り当てられた課題の実装、関連テスト、
報告に限定し、プロジェクト管理ファイルを直接更新しない。

ただし、管理基盤を構築して初期課題を登録するまでの bootstrap 期間に限り、親ワーカーが
明示的に割り当てた管理ファイルの新規作成をサブエージェントへ委譲できる。基盤の検証完了後は、
状態、担当、依存関係、backlog の更新を親ワーカーだけが行う通常運用へ移行する。

## ディレクトリ構成

```text
docs/project/
├── README.md
├── roadmap.md
├── backlog.md
└── items/
    ├── SL-001-stable-question-ids.md
    ├── SL-002-annotation-schema.md
    └── ...
scripts/
└── check_project_state.py
tests/
└── test_project_state.py
```

- `README.md`: 状態遷移、運用手順、front matter、必須セクションの規約
- `roadmap.md`: マイルストーンの目的、課題の所属、推奨着手順
- `backlog.md`: スクリプトが生成する全課題一覧
- `items/*.md`: 課題の正本
- `check_project_state.py`: 検証、backlog 生成、着手可能課題の表示
- `test_project_state.py`: 管理スクリプトの単体テスト

## 課題ファイル形式

### Front matter

```yaml
---
id: SL-001
title: 質問IDを再抽出後も安定させる
status: ready
priority: P1
type: defect
milestone: M1
depends_on: []
touches:
  - src/sheetlens/detectors/questions.py
  - tests/test_questions.py
owner: null
---
```

必須フィールドは `id`、`title`、`status`、`priority`、`type`、`milestone`、
`depends_on`、`touches`、`owner` とする。

許容値は次のとおりとする。

- `status`: `proposed`、`ready`、`in_progress`、`blocked`、`done`、`cancelled`
- `priority`: `P0`、`P1`、`P2`、`P3`
- `type`: `defect`、`refactor`、`enhancement`、`quality`
- `milestone`: `M1`、`M2`、`M3`、`M4`

`owner` は `in_progress` のときだけ非 null を必須とする。`touches` は `proposed` では空を
許可するが、`ready` 以降は最低 1 件を必須とする。

front matter の mapping key は一意でなければならず、既知・未知・非文字列を問わず重複を
拒否する。hash 不能な mapping key もファイル単位の構文エラーとして報告する。

`touches` は repository root を示す `.`、または canonical な repository-relative POSIX path
だけを許可する。空文字、絶対パス、Windows drive path、backslash、`.` または `..` segment、
空 segment、末尾 slash は拒否する。同一・親子パスの比較は component ごとに大文字小文字を
区別せず、Windows 上で同じ実体になる case-only alias も競合として扱う。

### 本文

すべての課題は次のセクションを持つ。

```markdown
# SL-001 質問IDを再抽出後も安定させる

## 背景と根本原因

## 根拠

## 受け入れ条件

## 対象外

## 実装計画

## 完了証拠
```

構造上のセクションは、backtick または tilde の fenced code block 外にある実際の `##` 見出しで
定義する。公開 parser は表示用に fence を含む元のセクション本文を返すが、状態検証では fence
内を mask する。fenced example だけでは必須本文、ブロッカー、完了証拠、受け入れ条件を満たせない。

`受け入れ条件` は Markdown チェックボックスで記述する。`-`、`*`、`+`、`N.`、`N)` の
CommonMark list item はすべて非空のチェックボックスでなければならず、`done` では全項目を
チェック済みにする。`blocked` の課題は追加で `ブロッカー` セクションを持ち、理由、解除条件、
次に確認することを記録する。`cancelled` の課題は `中止理由` セクションを持つ。

## 状態遷移

```text
proposed -> ready -> in_progress -> done
                         |
                         v
                      blocked

proposed / ready / blocked -> cancelled
done -> ready
```

状態の意味は次のとおりとする。

- `proposed`: 課題は記録済みだが、根本原因、変更範囲、受け入れ条件のいずれかが不足
- `ready`: 根拠、受け入れ条件、対象外、変更範囲が明確で、依存課題がすべて完了
- `in_progress`: owner が割り当てられ、現在作業中
- `blocked`: 外部入力や別の状態変化を待っており、解除条件が明記されている
- `done`: 受け入れ条件と検証をすべて満たしている
- `cancelled`: 対応しない理由が記録されている

`done` から `ready` へ戻す場合は、本文へ再オープン理由を追記する。状態遷移の履歴は Git の
履歴を正とし、課題ファイル内に重複した履歴表は持たない。

## 並行作業

複数課題を同時に `in_progress` にできるのは、次の条件をすべて満たす場合だけとする。

1. 課題間に直接または推移的な依存関係がない。
2. `touches` のファイルまたはディレクトリが同一でも親子関係でもない。
3. 同じ生成物、共有状態、リポジトリ管理ファイルを更新しない。
4. 課題ごとに異なる `owner` が設定されている。
5. 親ワーカーが開始前に並行可否を確認している。

変更範囲が広い課題、生成物を更新する課題、または競合可能性を静的に判定できない課題は
直列実行する。必要に応じて課題ごとに Git worktree を分離する。同一ワークスペースでの
サブエージェント並行実行は、変更範囲が完全に非重複の場合に限る。

## 標準ワークフロー

親ワーカーは次の順序で作業する。

1. `check` で管理状態を検証する。
2. `roadmap.md` と `backlog.md` を読む。
3. `next` が返す着手可能課題から、優先度と変更範囲を考慮して課題を選ぶ。
4. 並行する場合は依存関係と `touches` の非競合を確認する。
5. 課題を `in_progress` にし、owner を設定する。
6. 必要な実装計画を作成し、課題の `実装計画` からリンクする。
7. 実装、関連テスト、独立レビューを行う。
8. 受け入れ条件をチェックし、検証コマンドと結果を `完了証拠` に記録する。
9. 課題を `done` にし、backlog を再生成する。
10. `check`、関連テスト、lint を実行してからコミットする。

## 検証・生成 CLI

```bash
uv run python scripts/check_project_state.py check
uv run python scripts/check_project_state.py render
uv run python scripts/check_project_state.py next
```

### check

全エラーを収集してから表示し、エラーが 1 件でもあれば終了コード 1 を返す。構文や実行方法
そのものが不正な場合は終了コード 2 を返す。

共通検証:

- front matter の構文、mapping key の一意性、必須フィールド、型、許容値
- 課題 ID とファイル名先頭の一致、ID の重複
- 必須見出しの存在
- 参照先課題とマイルストーンの存在
- 依存関係の循環
- `backlog.md` と生成結果の一致

同じ ID が複数存在する場合は全出現をエラーにし、その ID を依存グラフから除外する。重複 ID
への参照は曖昧な依存として報告し、状態、循環、並行可否、着手可能性の判定で任意の 1 件を
選んではならない。

状態別検証:

- `ready`: 根本原因、非空 checkbox 形式の受け入れ条件、対象外、touches が記載済み
- `in_progress`: 非空 checkbox 形式の受け入れ条件、owner、touches が記載済み
- `blocked`: 非空 checkbox 形式の受け入れ条件、ブロッカーの理由、解除条件、次に確認することが記載済み
- `done`: 依存課題が完了し、受け入れ条件がすべてチェック済みで、完了証拠が存在
- `cancelled`: 中止理由が存在

並行作業検証:

- `in_progress` 間に直接または推移的な依存がない
- `touches` に component 単位で大小文字を無視した同一パスまたは親子パスがない
- owner が重複していない
- touches が空でない

エラーは課題ファイルと原因を示す。

```text
docs/project/items/SL-002-annotation-schema.md:
  - status=in_progress では owner が必須です
  - SL-001 と touches が競合しています: src/sheetlens/pipeline.py
```

### render

先に `check` のうち backlog 同期以外を実行する。不正な課題があれば書き込みを行わない。
正常な場合は課題から `backlog.md` を決定的に生成する。

一覧の列は次のとおりとする。

```text
ID | 優先度 | 状態 | マイルストーン | 課題 | 依存 | 担当
```

並び順は優先度、マイルストーン、ID とする。

### next

`status=ready`、かつ依存課題がすべて `done` の課題を優先度、マイルストーン、ID の順で
表示する。現在の `in_progress` 課題との `touches` 競合も表示し、並行可能か判断できるように
する。`next` 自体は状態を変更しない。候補を計算する前にプロジェクト全体を検証し、エラーが
1 件でもあれば終了コード 1 を返して候補行を一切表示しない。

## エラー処理

- 1 ファイルの不正で検証を中断せず、可能な限り全エラーを列挙する。
- front matter を読めない課題は依存グラフから除外し、その影響も別エラーとして報告する。
- `render` は検証失敗時に既存 backlog を変更しない。
- backlog の書き込みは一時ファイルへ生成してから置換する。
- 未知の front matter キーは綴り間違いを防ぐためエラーにする。
- 重複または hash 不能な front matter キーは任意の値を採用せず、課題ファイルのエラーにする。

## テスト方針

`tests/test_project_state.py` は一時ディレクトリに小さな疑似プロジェクトを作り、最低限次を
検証する。

- 正常なプロジェクト
- front matter の構文エラー、未知・重複・hash 不能 key、必須項目欠落
- ID 重複、ファイル名不一致、存在しない依存先
- 重複 ID の graph/eligibility 除外と曖昧な依存参照
- 直接循環と推移的循環
- 入力順を変えても同一になる cycle と並行競合の診断順
- 未完了依存を持つ `ready` と `done`
- 未チェック受け入れ条件または完了証拠なしの `done`
- fenced code 内の疑似見出し、本文、ブロッカー、チェックボックスの無視
- `-`、`*`、`+`、`N.`、`N)` の checkbox と plain/empty/unchecked item
- canonical でない `touches` の拒否と、Windows の case-only path alias の競合
- 不完全な `blocked` と `cancelled`
- 複数 `in_progress` の依存、パス競合、owner 重複
- stale な `backlog.md`
- 同一入力からの決定的な backlog 再生成
- 検証失敗時に backlog が変更されないこと
- `next` の優先順位と並行可否表示

## 初期ロードマップ

マイルストーンは順番を強制するフェーズではなく、成果目的による分類とする。課題の実際の
着手順は依存関係、優先度、変更範囲で決定する。

### M1 意味層の整合性

| ID | 課題 | 依存 |
|---|---|---|
| SL-001 | 質問 ID の安定化と旧 ID 移行 | なし |
| SL-002 | kind 別注釈スキーマと重複シート処理 | SL-001 |
| SL-003 | 構造要素への型付き安定 ID 導入 | SL-001、SL-002 |
| SL-004 | compiled 意味層 JSON と Markdown 無害化 | SL-002、SL-003 |

### M2 構造抽出の完全性

| ID | 課題 | 依存 |
|---|---|---|
| SL-005 | 名前定義プルダウンの解決 | なし |
| SL-006 | 条件付き書式 IR の完全化 | なし |
| SL-007 | セルの型、表示形式、表示意味の保持 | なし |
| SL-008 | グラフ、図形、ピボット等の存在記録 | なし |
| SL-009 | structural range と非表示範囲の修正 | なし |
| SL-010 | VML ボタン抽出の XML 解析化 | なし |

### M3 分析・実行信頼性

| ID | 課題 | 依存 |
|---|---|---|
| SL-011 | 手入力列と数式列を分離した質問生成 | なし |
| SL-012 | 数式正規化と依存グラフの token 解析化 | なし |
| SL-013 | アトミック再抽出と CLI エラー統一 | なし |

### M4 品質保証

| ID | 課題 | 依存 |
|---|---|---|
| SL-014 | 実 `.xlsm` fixture と Windows 検証 | なし |
| SL-015 | 再現可能な A/B 評価ハーネス | SL-001、SL-003 |
| SL-016 | ゴールデンテスト、CI、型、coverage | なし |
| SL-017 | 配布メタデータと ignore 整備 | なし |

初期の並行候補は SL-001、SL-005、SL-014 とする。ただし、課題ファイルへ実際の `touches`
を記録し、検証に通った後でのみ並行開始する。SL-005 と SL-006 は
`src/sheetlens/reader/features.py` で競合する可能性が高いため直列にする。

## 対象外

- GitHub Issues、GitHub Projects、外部 SaaS との同期
- 課題状態を保存する別 JSON データベース
- ガントチャート、工数見積もり、担当者の稼働率管理
- スクリプトによる自動的な状態変更
- 課題実装そのもの

## 完了条件

管理基盤の実装は、次を満たした時点で完了とする。

- 上記ディレクトリと運用文書が存在する。
- 初期 17 課題が根拠、受け入れ条件、対象外を含む形で登録されている。
- `check`、`render`、`next` が仕様どおり動作する。
- 管理スクリプトのテストがすべて成功する。
- 生成済み backlog と課題ファイルが同期している。
- ルートの開発者向け指示から標準ワークフローを参照できる。
