# SL-002 kind 別注釈スキーマと重複シート処理 実装計画

## 目的

注釈 YAML の kind ごとの契約を実行時に検証し、複数ファイルの同一シート注釈による
表示・回答情報の欠落を防ぐ。質問 ID の回答済み判定は、ID の存在だけでなく注釈の対象
シートと実内容も確認する。

## 調査結果と設計

- `AnnotationTarget` は共通の permissive model を廃止し、`kind` を discriminator とする
  `Annotated[Union[...], Field(discriminator="kind")]` に置き換える。
- `input_source`、`dropdown_semantics`、`trigger_timing`、`alert_action`、`sheet_role`、
  `free_note`、`hidden_reason` はそれぞれ必要な値だけを許可し、空の値・空の辞書を拒否する。
- 同一 `sheet` を複数の YAML が宣言した場合は、両ファイル名を含む `AnnotationError` で
  拒否する。これにより既存情報を黙って上書きしない。
- 既存の質問 ID の changed/deleted/unresolved 診断形式は維持する。注釈シートと質問シートの
  不一致、および `questions_answered` に対応する非空の内容がない場合は別の回答診断として
  記録し、`answered_ids` から除外する。
- `(VBA)` の trigger_timing は仮想注釈シートとして、質問 target の完全一致で照合する。
  セル範囲はカンマ・空白区切りを正規化し、マクロ／イベント名は分割しない。

## 実装順序

1. kind 別注釈モデルと YAML 読み込み時の duplicate sheet 検証を実装する。
2. 質問回答の対象一致・内容有無を pipeline の解決処理へ接続し、CLI 診断を表示する。
3. 既存の renderer とテストを具体的な target model に更新する。
4. kind ごとの schema failure、duplicate YAML、unknown/retired/mismatched ID、空回答、
   `(VBA)` を含む compile/check の回帰テストを追加する。

## 検証

- 対象テスト: `uv run pytest tests/test_annotations.py tests/test_compile_e2e.py tests/test_check_e2e.py tests/test_markdown.py -q`
- 必須検証: `uv run pytest -q`、`uv run ruff check .`、`uv run python scripts/check_project_state.py check`、`git diff --check`
