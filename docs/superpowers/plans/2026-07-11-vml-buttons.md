# SL-010 VML ボタン抽出 実装計画

## 目的

worksheetから参照されるVMLをnamespace URIで解析し、buttonのlabelとmacroをshape単位で
対応付ける。欠損・不正な参照とActiveXの存在はworkbookのextraction gapへ残す。

## 設計

- `legacyDrawing/@r:id` からexact relationship typeのVML partだけを解決する。
- package外、external、型違い、欠損part、不正XMLはgapにして他のsheetを継続する。
- VMLの `v:shape` ごとに `x:ClientData ObjectType="Button"`、`x:FmlaMacro`、
  `v:textbox` を対応付け、label空白を正規化する。
- macro欠損buttonはIRへ追加せず、shape IDまたはlabel付きgapを記録する。
- worksheetの `control` は `r:id` で重複排除し、ActiveX詳細未対応gapをsheetごとに残す。
  orphan relationshipは数えず、欠損IDや同一IDの矛盾はgapにする。
- `extract_buttons` にoptional gap sinkを追加し、`read_workbook`の既存gapへ接続する。
- 汎用の「VML drawing詳細未対応」gapは、VML artifact全体を解析しないため維持する。

## 実装手順

1. 別prefix、entity label、複数button、macro欠損、VML参照異常、ActiveX重複のテストを追加する。
2. `buttons.py` をElementTreeとexact URI relationship解決へ置き換える。
3. `workbook.py`からgap sinkを渡し、実xlsm期待値を更新する。
4. 関連テスト、全テスト、lint、project-stateを検証する。
