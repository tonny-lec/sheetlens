# SL-012 数式token解析 実装計画

## 目的

数式の正規化と依存抽出をopenpyxl Tokenizerに統一し、相対参照をsource cell基準で保持した
決定的なdependency edgeをmanifestへ保存する。

## 設計

- A1参照をR1C1相当の相対表現へ正規化する。相対行列は `R[n]C[n]`、絶対行列は
  `RnCn` とし、文字列literalを変更しない。
- edge sourceは `cell:'Sheet'!A1`、`validation:'Sheet'!A1:A9`、
  `conditional_format:'Sheet'!A1:A9` の固定形式にする。
- local参照は `target_workbook: null`、既知sheetのIR表記、正規化A1 range、
  `unresolved: false` とする。
- 外部book、未知sheet/name、3D、structured ref、循環・動的defined name、tokenize失敗は
  raw operandを保持して `unresolved: true` とする。
- defined nameはcase-insensitiveに一意なworkbook-scoped定義だけをcycle guard付きで展開する。
- validation/CFは適用rangeごとにedgeを作り、source rangeとformula上のA1参照を保持する。
- manifestへ決定順の`dependency_edges`を追加し、既存`dependencies`と`external_refs`は
  edgeから後方互換生成する。

## 実装手順

1. R1C1相当正規化、lowercase、literal、絶対/相対混在のREDテストを追加する。
2. local/external同名sheet、quoted sheet、defined name、validation/CF、unresolvedのREDテストを追加する。
3. shared formula token parser、DependencyEdge IR、machine renderer接続を実装する。
4. 関連テスト、全テスト、lint、project-state、advisor reviewを完了する。
