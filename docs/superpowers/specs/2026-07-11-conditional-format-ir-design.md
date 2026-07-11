# SheetLens 条件付き書式 IR 完全化 設計書

## 目的

条件付き書式から複数数式、差分スタイル、および主要な可視化ルールを失わずに抽出し、
`raw.json`、Markdown、依存関係へ伝播する。未対応または壊れたルールがあっても、共通情報を
保持して workbook の抽出を継続し、理由を `extraction_gaps` に残す。

旧形式の単数 `formula` は読み込み時に自動移行し、既存データや呼び出し側へ手動更新を
要求しない。

## 現状と根本原因

`ConditionalFormat` は単数の `formula` しか持たず、reader も openpyxl の `rule.formula` の
先頭要素だけを保存する。このため `between` の上限式や複数式を持つ `expression` が欠落する。

`colorScale`、`dataBar`、`iconSet`、`dxf` を保持する IR がないため、可視化条件と差分スタイルも
抽出時に失われる。さらに Markdown と machine renderer は単数の `formula` を前提としており、
IR だけを変更しても複数式が end-to-end で利用されない。

現在の例外処理はシート単位であるため、一つの不正ルールでそのシートの条件付き書式全体を
失う可能性がある。

## 設計原則と範囲

受け入れ条件を満たす最小の end-to-end 修正として、次の5種類を完全抽出の対象とする。

- `cellIs`
- `expression`
- `colorScale`
- `dataBar`
- `iconSet`

その他のルール種別は共通情報を保持して gap を追加する。既知の全ルール種別を個別モデル化する
対応や、条件付き書式の視覚レンダリングには範囲を広げない。

## IR

`ConditionalFormat` を次の形へ変更する。

```text
ConditionalFormat
  range: str
  rule_type: str
  formulas: list[str]
  operator: str | None
  stop_if_true: bool
  color_scale: ConditionalColorScale | None
  data_bar: ConditionalDataBar | None
  icon_set: ConditionalIconSet | None
  dxf: OoxmlNode | None
```

可視化ペイロードは openpyxl object を直接公開せず、小さな型付きモデルへ正規化する。

```text
ConditionalValue
  type: str | None
  value: str | float | int | None
  gte: bool | None

ConditionalColor
  type: str
  value: str | float | int | bool
  tint: float

ConditionalColorScale
  conditions: list[ConditionalValue]
  colors: list[ConditionalColor]

ConditionalDataBar
  conditions: list[ConditionalValue]
  color: ConditionalColor
  show_value: bool | None
  min_length: int | None
  max_length: int | None

ConditionalIconSet
  icon_style: str | None
  conditions: list[ConditionalValue]
  show_value: bool | None
  percent: bool | None
  reverse: bool | None
```

Excel の色は RGB だけでなく theme、indexed、auto も取り得るため、`type`、`value`、`tint` を
保持する。openpyxl の `Color(auto=True)` は value が bool になるため、bool も明示的に許可する。

### dxf

差分スタイルの全プロパティを個別モデルとして再定義すると変更範囲と保守負担が大きくなる。
一方、openpyxl object や内部辞書をそのまま保存するとライブラリ実装へ依存する。このため dxf は
openpyxl が生成する OOXML 要素を JSON-safe な再帰構造へ正規化する。

```text
OoxmlNode
  tag: str
  attributes: dict[str, str]
  text: str | None
  children: list[OoxmlNode]
```

openpyxl が生成した要素名と属性名をそのまま保持し、値は文字列化する。`to_tree()` の出力には
namespace が付かない場合があるため、元 XML の namespace 保持は保証しない。これにより font、
fill、border、alignment、protection など現在および将来の dxf 子要素を、IR schema の追加変更なしで
保存できる。

## 後方互換性と自動移行

新しい canonical field は `formulas` とし、新規 JSON は `formulas` のみを出力する。
Pydantic の model-level before validator で旧入力を変換する。

```text
formula があり formulas がない:
  formula is None -> formulas=[]
  それ以外       -> formulas=[formula]
```

これにより旧 `raw.json` と `ConditionalFormat(formula="0")` を引き続き受け付ける。互換用の
`formula` property は先頭式、または式がなければ `None` を返す。`cf.formula = value` の代入も
setter で `formulas` の先頭要素を更新し、既存の書き込み側へ手動修正を要求しない。`None` の代入は
`formulas=[]` とする。`formula` と `formulas` が constructor または JSON に同時に与えられた場合は
新形式の `formulas` を正とし、曖昧な merge は行わない。

## Reader とデータフロー

既存の一引数呼び出しを維持しつつ、規則単位の診断を workbook へ集約できるようにする。

```python
def read_conditional_formats(
    ws_f,
    *,
    extraction_gaps: list[str] | None = None,
) -> list[ir.ConditionalFormat]:
    ...
```

`read_workbook()` は自身が管理する gap list を渡す。直接呼び出しで引数を省略した場合は従来どおり
list だけを返す。渡された空 list を保持するため、`extraction_gaps is None` で判定する。

各ルールを次の順で独立して処理する。

1. range、type、全 formulas、operator、stop-if-true を抽出する。
2. dxf を OOXML node へ正規化する。
3. 対応する可視化ペイロードを抽出する。
4. ルール種別と必須ペイロードの整合性を検証する。
5. 共通情報と抽出できたペイロードを IR へ追加する。
6. 未対応または不正なら、そのルールだけに gap を一件追加する。

この処理全体をルール単位の `try/except` で隔離する。予期しない例外が発生した場合も、事前に
取得できた range、type、formulas、operator、stop-if-true を持つ IR を可能な限り追加し、
`extraction_error` gap を一件記録して後続ルールへ進む。共通情報の構築自体に失敗した場合は、
少なくとも iteration 元の range と取得可能な type を使った最小 IR を追加する。

最小限の整合性検証は次のとおりとする。

- `colorScale`: payload があり、conditions と colors の件数が一致する。
- `dataBar`: payload、開始・終了 condition、color がある。
- `iconSet`: payload、icon style、conditions がある。
- `cellIs` と `expression`: 可視化ペイロードを要求しない。

不正または未対応のルールも range、type、formulas、operator、stop-if-true、抽出できた dxf を保持する。
可視化ペイロードは検証に合格した場合だけ設定する。予期しない例外に対する既存のシート単位 catch
は最終防衛として残す。

openpyxl が workbook 読み込み時点で拒否する不明な type は、この関数へ到達しないため既存の
workbook load error 経路で扱う。openpyxl が読み込める未対応 type と、payload が欠けた既知 type は
規則単位の gap とする。

## Gap の扱い

gap は次の固定形式を使う。

```text
{sheet}: 条件付き書式 {range} を完全に抽出できません (type={rule_type}; reason={reason_code})
```

reason code は次の固定値とする。

- `unsupported_type`
- `missing_color_scale`
- `invalid_color_scale`
- `missing_data_bar`
- `invalid_data_bar`
- `missing_icon_set`
- `invalid_icon_set`
- `invalid_dxf`
- `extraction_error`

dxf の正規化だけに失敗した場合は、その他のルール情報と可視化ペイロードを保持し、`invalid_dxf`
を記録する。一つのルールで複数の問題が見つかった場合は、最初に確定した理由を一件だけ記録する。

## 下流への伝播

machine renderer は `formulas` の全要素を依存関係抽出へ渡す。これにより、2番目以降の式にだけ
存在するシート参照も依存関係へ反映される。

Markdown renderer は複数式を順序どおりすべて表示する。可視化ルールは condition、color、主要な
表示オプションを簡潔なテキストで表示するが、実際の色スケール、バー、アイコンは描画しない。
未対応ルールも type と共通情報を表示し、gap は既存の README gap 表示へ伝播する。

質問生成と annotation weaving は条件付き書式の range だけを使用しているため変更しない。

## 対象外

- 条件付き書式の視覚レンダリング
- `containsText`、`top10` など、対象5種類以外の専用ペイロード
- openpyxl が workbook 読み込み時に拒否する未知 type の規則単位復旧
- Excel の拡張条件付き書式仕様を独自に XML parse する処理

## 変更範囲

- `src/sheetlens/model/ir.py`: formulas、可視化モデル、dxf node、旧 formula の自動移行。
- `src/sheetlens/reader/features.py`: ルール単位の抽出、正規化、検証、gap 生成。
- `src/sheetlens/reader/workbook.py`: 条件付き書式 gap の集約。
- `src/sheetlens/renderers/machine.py`: 全 formulas の依存関係抽出。
- `src/sheetlens/renderers/markdown.py`: 複数式と可視化ペイロードの要約。
- `tests/test_ir.py`: schema、旧形式移行、JSON 往復。
- `tests/test_features.py`: 各ルール種別、dxf、gap、ルール単位の隔離。
- `tests/test_machine.py`: 2番目以降の式からの依存関係。
- `tests/test_markdown.py`: 複数式と可視化設定の表示。
- `tests/test_extract_e2e.py`: 新 payload の `structure/raw.json` への伝播。

元の課題記載より変更ファイルは増えるが、IR の追加だけでは既存 renderer が先頭式しか扱えず、
受け入れ条件を end-to-end で満たさない。上記は新 IR の消費箇所に限定した変更である。

## テスト方針

実装は test-driven-development で進め、production code を変更する前に対応する失敗テストを
確認する。

### IR と互換性

- `formula` を持つ旧 constructor と旧 JSON を `formulas` へ自動移行する。
- 新形式の dump は `formulas` を含み、`formula` を含まない。
- `formula` compatibility property は先頭式を返し、setter は `formulas` を更新する。
- `formula` と `formulas` の同時入力では `formulas` が優先され、dump に旧 key を残さない。
- RGB、theme、indexed、auto color と再帰的 dxf を JSON 往復する。

### Reader

- `between` の2式を順序どおり保持する。
- `expression` の複数式を保持する。
- `colorScale`、`dataBar`、`iconSet` を保存・再読込した workbook から抽出する。
- 代表的な dxf を正規化する。
- 複数ルールと複数 range を保持する。
- 可視化 payload が欠けた既知 type は共通情報を保持して理由付き gap になる。
- `top10` などの未対応 type は共通情報を保持して `unsupported_type` gap になる。
- 問題のある一件が同じシートの正常なルールを失わせない。
- dxf 正規化を含む予期しない例外でも後続ルールを保持し、`extraction_error` を記録する。
- 規則単位の gap が `Workbook.extraction_gaps` へ伝播する。
- 一つのルールに複数の問題があっても gap は一件だけになる。

### 下流

- 先頭式には参照がなく、2番目の式だけが別シートを参照する場合も依存関係を検出する。
- Markdown が全式と可視化ペイロードの主要設定を表示する。
- 単一式の既存表示と依存関係抽出を維持する。
- `formulas=[]` を Machine と Markdown が安全に処理する。
- extract E2E で新しい payload が `structure/raw.json` へ出力される。

### 完了検証

```bash
uv run pytest tests/test_ir.py tests/test_features.py tests/test_machine.py tests/test_markdown.py tests/test_extract_e2e.py -q
uv run pytest -q
uv run ruff check .
uv run python scripts/check_project_state.py check
```

完了前に独立レビュー担当へ、互換性、openpyxl 境界、gap の隔離、過剰な変更範囲に関する問題を
探すよう依頼する。
