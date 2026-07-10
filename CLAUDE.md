# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要: SheetLens

業務で使われている Excel ファイルの「データ構造・データ間の関係性・セルの業務上の意味」を
AI エージェントが解釈できる形に変換する、**AI のための Excel 理解支援ツール**。

### 背景と解決したい問題

Excel 業務ツールの Web 化案件で、AI エージェントに Excel を直接読ませると精度が低い。
具体的に失敗しやすいのは以下の 2 層:

1. **構造の読み取り失敗**（機械的に抽出できるはずの情報）
   - 表の構造の再現、セルの数式、条件付き書式、セル結合、レイアウト
2. **業務意味との関連付け失敗**（Excel ファイル単体からは導出できない情報）
   - 手入力される表とツールが自動入力する表の区別
   - プルダウン選択値の業務上の意味
   - セルのデータ・操作と業務フロー・業務状態との対応関係

### ゴール

AI エージェントが人間と同等に、Excel ベースの業務を理解できる状態を作る。
出力は人間向けではなく **AI エージェント（要件定義・設計を行う LLM）が消費する
構造化された中間表現** であることを常に意識する。

## 設計上の指針

- 上記 2 層（機械抽出できる「構造層」と、人間の知識が必要な「意味層」）を分離して扱う。
  構造層は Excel ファイルから決定的に抽出し、意味層は人間へのヒアリング結果や
  注釈として構造層に紐付ける設計を基本とする。
- 出力形式を決める際は「LLM のコンテキストに載せたときに誤読しないか」を評価基準にする。
  見た目の再現より、参照関係・意味の明示を優先する。

## 現在の状態と設計

- 設計は確定済み。**必ず先に設計書を読むこと**:
  `docs/superpowers/specs/2026-07-07-sheetlens-design.md`
  （アーキテクチャ・中間表現フォーマット・注釈スキーマ・スコープ外事項を定義）
- 技術スタック: **Python 3.12+ / uv 管理**。
  依存: openpyxl（構造抽出）/ oletools（VBA 抽出）/ pydantic / pyyaml / typer。dev: pytest
- 実サンプルの業務 Excel はこの PC に存在しない（業務 PC と分離）。テストは
  openpyxl で生成する合成フィクスチャと、ユーザーの記憶ベースのダミーで行う。

## コマンド

- 依存同期: `uv sync`
- テスト全件: `uv run pytest` / 単一ファイル: `uv run pytest tests/test_reader.py -v` /
  単一テスト: `uv run pytest tests/test_reader.py::test_name -v`
- Lint: `uv run ruff check .`
- 実行例: `uv run sheetlens extract <file.xlsx>` → `<file>.sheetlens/` を生成

## 改善プロジェクト管理

- 継続的な改善課題は `docs/project/README.md` の手順に従う。
- 作業開始時に `uv run python scripts/check_project_state.py check` と `next` を実行する。
- 管理基盤構築と初期課題登録までの bootstrap 期間に限り、親ワーカーが明示的に割り当てた
  管理ファイルの新規作成を実装ワーカーへ委譲できる。
- bootstrap 完了後は、親ワーカーだけが課題の状態、owner、依存関係、`backlog.md` を更新する。
- 実装テストとレビュー後に、親ワーカーが受け入れ条件と完了証拠を更新して課題を `done` にする。
- `done` への更新後に `render`、`check`、関連テスト、lint を実行し、成功後にコミットする。

## 共通ルール

ワークスペース共通の運用ルール（サブエージェント委譲・検証義務・境界）は
`/home/tonny/workspace/CLAUDE.md` に従う。ただし同ファイルの `<>` プレースホルダ
（ビルドコマンド等）は本プロジェクトではまだ未定義。
