# SheetLens 名前定義プルダウン解決 設計書

## 目的

入力規則のリスト元が workbook scope または sheet-local scope の名前定義である場合に、
参照先の静的セル範囲から選択肢を抽出する。解決できない名前や未対応の動的式があっても、
入力規則と workbook の抽出を継続し、理由を `extraction_gaps` に残す。

既存の `ValidationRule`、`raw.json`、`read_validations()` の利用方法を維持し、既存データや
呼び出し側に手動移行を要求しない。

## 現状と根本原因

`_resolve_list()` は `formula1` から先頭の `=` を除去し、`!` がなければ残りを現在シートの
セル参照として `ws[ref]` に渡す。このため `=Choices` は名前定義ではなくセル座標
`Choices` として評価される。

セル座標として解釈できない場合や参照先シートが存在しない場合は、`KeyError` または
`ValueError` を捕捉して `[]` を返す。これにより、有効だが値が空の範囲と、未解決名、
`INDIRECT`、`OFFSET` などの解決失敗を呼び出し側が区別できない。

`read_workbook()` の外側の例外処理まで例外が届く場合は、そのシートの入力規則が全件
`validations=[]` になる。規則一件の解決失敗に対して失われる情報が多すぎる。

## 設計原則

- Excel の scope に従い、sheet-local name を workbook name より優先する。
- defined name は各 scope 内で大文字小文字を区別せず照合する。
- 静的な単一の連続セル範囲だけを評価し、任意の Excel 式を実行しない。
- 解決失敗は入力規則単位で隔離し、同じシートの他の規則を保持する。
- `formula1` と適用範囲を保持し、再調査できる情報を失わない。
- 正常な空範囲と解決失敗を内部状態および gap の有無で区別する。
- 既存 API と IR schema を変更せず、手動 migration を不要にする。

## データフロー

```text
DataValidation.formula1
  |
  +-- inline list ---------------------------> choices
  |
  +-- direct static range -------------------> choices
  |
  +-- defined name
  |     +-- current sheet local name
  |     +-- workbook name fallback
  |             |
  |             +-- one static range --------> choices
  |             +-- unsupported/unresolved --> choices=[] + gap
  |
  +-- INDIRECT/OFFSET/other unsupported -----> choices=[] + gap
```

`read_workbook()` は数式保持用 workbook と値取得用 workbook を従来どおり読み込む。
名前定義の検索と値取得には値取得用 workbook を使い、現在シートは入力規則を読み取っている
数式保持用 worksheet の title で特定する。

## API と互換性

`read_validations()` の戻り値は `list[ir.ValidationRule]` のまま維持する。警告を呼び出し元へ
渡すため、任意の keyword-only 引数を追加する。

```python
def read_validations(
    ws_f,
    wb_v,
    *,
    extraction_gaps: list[str] | None = None,
) -> list[ir.ValidationRule]:
    ...
```

既存の `read_validations(ws_f, wb_v)` は変更なしで動作する。`read_workbook()` は自身が管理する
gap list を渡し、規則単位の診断を `ir.Workbook.extraction_gaps` へ集約する。

内部 resolver は選択肢だけでなく、解決成功か、解決できなかった理由も返す。正常に解決した
結果の値がすべて空なら `choices=[]` かつ gap なし、解決失敗なら `choices=[]` かつ gap ありとする。

`extraction_gaps` を省略した直接呼び出しでは、既存の戻り値互換性を優先して診断を外部へ
返さない。この場合も内部では成功と失敗を区別する。実装は呼び出し元から渡された空 list を
保持するため `extraction_gaps is None` で判定し、`extraction_gaps or []` は使用しない。

`ValidationRule` や `Workbook.defined_names` の schema は変更しない。sheet-local name は openpyxl の
worksheet object 上で解決し、scope を表現できない現行 `Workbook.defined_names` へ flatten しない。
したがって既存 `raw.json` の migration は不要である。

## リスト参照の解決

### 正規化と分類

元の `formula1` は IR へそのまま保存する。resolver 用の文字列だけ、周辺空白と高々一つの
先頭 `=` を除去する。複数の先頭 `=` は有効な参照として推測しない。

1. 引用された inline list は従来どおりカンマで分割する。
2. sheet qualifier 付き、または現在シート上の有効な A1 range は直接参照として解決する。
3. 既知の関数式 `INDIRECT` と `OFFSET` は評価せず、固有の理由で gap にする。
4. 直接 range または既知の関数式でなければ defined name として扱う。
5. その他の式、複数領域、名前の多段参照は静的な単一範囲でないため gap にする。

### 名前定義の検索順

現在の worksheet の `defined_names` を検索し、一致しなければ workbook の `defined_names` を
検索する。openpyxl の mapping lookup は大小文字を区別するため、各 scope 内の key を
`casefold()` して比較する。同一 scope に case-insensitive で同名の定義が複数ある壊れた
workbook は、曖昧な名前として gap にする。

同名の local name と workbook name が存在する場合、local name を採用する。local name の
参照先が `#REF!`、動的式、複数領域などで解決できなくても、shadow された workbook name へ
fallback せず、local name の理由を gap にする。

見つかった定義が単一の静的 range を指す場合だけ destination を値へ解決する。定義の
`attr_text` 自体が `INDIRECT` または `OFFSET` なら、それぞれ固有の未対応理由を使う。

local name の定義が sheet qualifier を省略している場合、`DefinedName.destinations` は安全に
利用できない。この場合は `attr_text` を A1 range として直接検証し、定義元の現在シートへ
明示的に束縛する。保存して再読込した workbook でも同じ経路を使う。workbook scope の
無修飾 range は固定の参照シートを安全に決定できないため、現在シートへ推測で束縛せず
`unsupported_reference` とする。

### シート名と range

引用されたシート名を含む range を扱う。

```text
'Master Data'!$A$2:$A$3
'O''Brien'!$A$1:$A$2
```

引用符を除去し、Excel の二重 apostrophe `''` を単一の `'` へ戻して実際の worksheet title を
検索する。絶対参照の `$` はセル値取得前に正規化する。

値は range の行優先順で取得し、`None` は選択肢から除外し、それ以外は従来どおり文字列化する。

## Gap の扱い

未解決または未対応の規則も `ValidationRule` として保持する。`ranges`、`type`、`formula1` を
保存し、`choices=[]` とする。gap は一つの DataValidation ごとに一件だけ追加し、次の固定形式を
使う。

```text
{sheet}: 入力規則 {sorted ranges} の選択肢を解決できません (formula1={formula1}; reason={reason code})
```

複数の適用範囲は canonical string の昇順で並べ、`, ` で連結する。`formula1` は元の値を
`repr()` 相当で表現する。reason code は次の固定値とする。

- `name_not_found`: 名前定義が見つからない
- `ambiguous_name`: 同一 scope に大小文字だけが異なる同名定義が複数ある
- `sheet_not_found`: 参照先シートが存在しない
- `invalid_range`: `#REF!`、不正座標、worksheet の上限外など、range が有効でない
- `unsupported_indirect`: `INDIRECT` は未対応
- `unsupported_offset`: `OFFSET` は未対応
- `unsupported_reference`: 複数領域、名前の多段参照、その他の静的な単一 range でない参照

参照先シートと A1 range が有効で、範囲内の値がすべて `None` の場合は正常な空 range とし、
gap を追加しない。

gap は最低限次を含む。

- 入力規則が存在するシート名
- 入力規則の適用範囲
- 元の `formula1`
- 解決できなかった理由

予測できる解決失敗は resolver の結果として処理し、例外をシート単位の catch まで送らない。
壊れた workbook などの予期しない例外に対する既存のシート単位 catch は最終防衛として残す。

## 下流への影響

解決できた選択肢は Markdown、質問生成、`raw.json` へ従来の `choices` として伝播する。
これまで空だった `choices` が実値になるため、該当するリスト入力規則から生成される質問文と
その content-based question ID は変化し得る。質問 identity は変わらないため、既存の question
catalog が内容変更として検出する既存経路を使用する。

machine renderer の依存グラフは `formula1` を参照しており、名前定義から解決した destination を
保持する schema はない。本課題では依存グラフの参照先補完を行わない。

## 対象外

- `INDIRECT`、`OFFSET`、その他の任意式の評価
- 複数領域を一つの選択肢列へ結合する処理
- 名前定義から別の名前定義への多段解決
- scope 付き名前定義を保持するための IR schema 変更
- 名前定義を経由した依存グラフ edge の追加

## 変更範囲

- `src/sheetlens/reader/features.py`: range/defined-name resolver、規則単位の gap 生成。
- `src/sheetlens/reader/workbook.py`: validation gap の集約。
- `tests/test_features.py`: 正常系、scope、引用名、未解決・動的式、隔離動作の統合テスト。

## テスト方針

実装は test-driven-development で進め、production code を変更する前に対応する失敗テストを
確認する。

### 正常系

- workbook scope の名前定義を解決する。
- sheet-local scope の名前定義を解決する。
- formula1 と定義名の大小文字が異なっても、各 scope 内で名前を解決する。
- 同名 local/workbook name では local name を優先する。
- local name がない別シートでは workbook name へ fallback する。
- sheet qualifier のない local name を、保存して再読込した workbook から解決する。
- 空白または apostrophe を含む引用シート名を解決する。
- 現在シート上の直接 range を解決する。
- 正常に解決した空 range は `choices=[]` かつ gap なしになる。
- 既存の inline list と直接 range の結果が変わらない。

### 未解決・未対応

- 存在しない名前定義は `choices=[]` かつ理由付き gap になる。
- `INDIRECT` と `OFFSET` は評価せず、それぞれ理由付き gap になる。
- defined name の参照先が `INDIRECT` または `OFFSET` の場合も固有の理由付き gap になる。
- sheet qualifier のない workbook scope name は `unsupported_reference` になる。
- 定義の参照先シートまたは range が存在しない場合は gap になる。
- 無効な local name と同名の有効な workbook name があっても fallback しない。
- 問題のある規則も `ranges` と `formula1` を保持する。
- 一件の解決失敗があっても、同じシートの正常な規則を保持する。
- 複数の適用範囲を持つ同じ規則の gap を、決定的な範囲順で一件だけ追加する。

### 互換性と伝播

- 旧来の二引数 `read_validations(ws_f, wb_v)` が list を返す。
- 既存要素を持つ `extraction_gaps` list を上書きせず末尾へ追記する。
- 規則単位の gap が `read_workbook()` から `Workbook.extraction_gaps` へ伝播する。

### 完了検証

```bash
uv run pytest tests/test_features.py -q
uv run pytest -q
uv run ruff check .
uv run python scripts/check_project_state.py check
```
