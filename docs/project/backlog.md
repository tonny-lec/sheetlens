# SheetLens 改善 Backlog

> このファイルは `scripts/check_project_state.py render` で生成します。手動編集しません。

| ID | 優先度 | 状態 | マイルストーン | 課題 | 依存 | 担当 |
|---|---|---|---|---|---|---|
| [SL-001](items/SL-001-stable-question-ids.md) | P1 | done | M1 | 質問 ID の安定化と旧 ID 移行 | — | — |
| [SL-002](items/SL-002-annotation-schema.md) | P1 | proposed | M1 | kind 別注釈スキーマと重複シート処理 | SL-001 | — |
| [SL-003](items/SL-003-typed-element-ids.md) | P1 | proposed | M1 | 構造要素への型付き安定 ID 導入 | SL-001, SL-002 | — |
| [SL-004](items/SL-004-compiled-semantics.md) | P1 | proposed | M1 | compiled 意味層 JSON と Markdown 無害化 | SL-002, SL-003 | — |
| [SL-005](items/SL-005-defined-name-validations.md) | P1 | done | M2 | 名前定義プルダウンの解決 | — | — |
| [SL-006](items/SL-006-conditional-format-ir.md) | P1 | done | M2 | 条件付き書式 IR の完全化 | — | — |
| [SL-007](items/SL-007-cell-display-semantics.md) | P1 | done | M2 | セルの型、表示形式、表示意味の保持 | — | — |
| [SL-008](items/SL-008-artifact-presence.md) | P1 | done | M2 | グラフ、図形、ピボット等の存在記録 | — | — |
| [SL-011](items/SL-011-input-formula-regions.md) | P1 | done | M3 | 手入力列と数式列を分離した質問生成 | — | — |
| [SL-014](items/SL-014-real-xlsm-windows.md) | P1 | done | M4 | 実 xlsm の Windows E2E 検証 | — | — |
| [SL-015](items/SL-015-reproducible-evaluation.md) | P1 | proposed | M4 | 再現可能な A/B 評価基盤 | SL-001, SL-003 | — |
| [SL-018](items/SL-018-autonomous-git-completion.md) | P1 | done | M4 | Codexによる課題完了時の自動Git統合 | — | — |
| [SL-009](items/SL-009-structural-range.md) | P2 | done | M2 | structural range と非表示範囲の修正 | — | — |
| [SL-010](items/SL-010-vml-buttons.md) | P2 | done | M2 | VML ボタン抽出の XML 解析化 | — | — |
| [SL-012](items/SL-012-formula-dependency-parser.md) | P2 | ready | M3 | 数式正規化と依存グラフの token 解析化 | — | — |
| [SL-013](items/SL-013-atomic-extract-cli-errors.md) | P2 | ready | M3 | アトミック再抽出と CLI エラー統一 | — | — |
| [SL-016](items/SL-016-golden-ci-quality.md) | P2 | ready | M4 | golden test と CI 品質ゲート | — | — |
| [SL-019](items/SL-019-process-project-backlog.md) | P2 | done | M4 | backlog 課題の自動直列処理 | — | — |
| [SL-017](items/SL-017-package-repository-hygiene.md) | P3 | ready | M4 | パッケージとリポジトリの衛生管理 | — | — |
