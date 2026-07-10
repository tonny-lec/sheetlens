# SheetLens

業務 Excel（.xlsx / .xlsm）を、AI エージェントが誤読しない中間表現に変換する CLI ツール。

Excel 業務ツールの Web 化案件などで LLM に要件定義・設計をさせるとき、生の Excel を
読ませると「数式・セル結合・条件付き書式・レイアウトの読み取り失敗」と「業務上の意味
（誰が入力するのか、プルダウンの選択肢は何を意味するのか）の欠落」の 2 つで精度が
落ちます。SheetLens はこの 2 層を分離して解決します。

- **構造層** — ファイルから決定的に抽出できる情報（数式・結合・入力規則・条件付き書式・
  VBA・ボタン）。`extract` が Markdown + JSON に変換します
- **意味層** — ファイルからは導出できない業務知識。ツールが生成する質問リストを元に
  AI エージェントが人間にインタビューし、回答を注釈 YAML として蓄積。`compile` が
  構造層に織り込みます

SheetLens 自体は LLM を呼びません。出力は入力に対して決定的で、どの AI エージェント
からも利用できます。

## クイックスタート

[uv](https://docs.astral.sh/uv/) が必要です。

```bash
git clone https://github.com/tonny-lec/sheetlens.git
cd sheetlens
uv sync

# 1. Excel から構造層と質問リストを生成
uv run sheetlens extract 見積管理.xlsm
#    → 見積管理.sheetlens/ が生成される

# 2. questions.md を元に業務担当者へヒアリングし、回答を annotations/*.yaml に記録
#    （この工程は AI エージェント + 人間が行う。ツールは質問リストと雛形を提供）

# 3. 注釈を織り込んだ最終ビューを再生成
uv run sheetlens compile 見積管理.sheetlens

# 補助: 孤立注釈・未回答質問・スキーマ違反の確認
uv run sheetlens check 見積管理.sheetlens
```

## 出力の構成

```
見積管理.sheetlens/
├── manifest.json        # 元ファイルのハッシュ・シート間依存グラフ・extraction_gaps
├── question-ids.json    # 安定した質問 ID と旧 ID alias の履歴
├── structure/           # 【構造層】extract の再実行で完全に再生成される
│   ├── sheet-<シート名>.md   # LLM 向けビュー（レイアウトマップ・数式パターン・入力規則…）
│   ├── vba/<モジュール名>    # VBA ソース
│   └── raw.json         # 省略なしの全抽出データ（機械可読の正）
├── annotations/         # 【意味層】人間の回答。ツールは絶対に書き換え・削除しない
│   └── <シート名>.yaml
├── questions.md         # 構造から自動生成した「人間に聞くべき質問リスト」
└── README.md            # AI エージェント向けの入口（読み方・欠落警告）
```

現在の質問 ID は、質問の内容から決定的に生成される `q2-<rule>-<16hex>` 形式です。
旧形式の `q-NNN` は `question-ids.json` に保存された alias で引き続き解決し、alias は一度保存した対応先から変更しません。
移行時も SheetLens は `annotations/*.yaml` の質問 ID を書き換えません。
catalog の `legacy_source_sha256` は alias を作ったアップグレード前の抽出 snapshot の由来であり、回答時点を証明するものではありません。

シート Markdown の例（抜粋）:

```markdown
## 数式（正規化済み）
- E11:E30 = `=C{row}*D{row}`（例: `=C11*D11`）
  - **⚠ 例外: E15: =C15*D15*1.1**（パターンから逸脱。特例または誤りの可能性）

## 入力規則（プルダウン等）
- B5: list（=区分マスタ!$A$2:$A$3） 選択肢: 通常, 特急
> 💬 業務上の意味: 選択肢の意味: 「通常」=標準納期を適用、「特急」=割増率を自動設定

## 未確認事項
> ❓ 未確認 (q2-input_region-<16hex>): [A3:B8] 範囲 A3:B8 のデータは誰が・いつ・何を見て入力しますか？
```

同一パターンの数式は「範囲 + パターン + 例外」に集約し、逸脱セルを強調します
（手修正された数式は業務上の特例やバグの発見に直結するため）。未回答の質問は
`❓ 未確認` として明示し、AI が推測で要件を捏造することを防ぎます。

## 設計原則

1. **構造層 = 再生成可能、意味層 = 蓄積資産** — `structure/` は再抽出で作り直され、
   `annotations/` は人間の知識としてツールが決して消さない
2. **静かな欠落の禁止** — 抽出できなかった要素は `extraction_gaps` に記録し、
   README 冒頭に「⚠ この抽出には N 件の欠落があります」と明示する
3. **決定的な出力** — タイムスタンプ・乱数を含まない。同じ入力からは常に同じ出力

詳細は [設計書](docs/superpowers/specs/2026-07-07-sheetlens-design.md) を参照してください。

## 評価（QA ハーネス）

「中間表現だけを読んだ AI の QA 正答率が、生 xlsx を読ませた場合を上回るか」を
成功基準としています。`eval/` にダミー業務 Excel の生成スクリプトと正答つき
質問セットがあります。手順は [eval/README.md](eval/README.md) を参照。

```bash
uv run python eval/make_dummy.py
uv run sheetlens extract eval/見積管理.xlsx
```

## 開発

```bash
uv sync
uv run pytest          # テスト全件
uv run ruff check .    # Lint
```

- Python 3.12+ / 依存: openpyxl, oletools, pydantic, pyyaml, typer
- テスト用の Excel はコミットせず、openpyxl でテスト内生成しています

## ステータス

v1（初期実装）。既知の制限:

- VBA 抽出の実 .xlsm での検証は未了（正常系はモックテスト）
- QA 評価（A/B 比較）は未実施
- .xls（旧形式）・パスワード保護ファイル・グラフ/図形/ピボットの詳細抽出は対象外
