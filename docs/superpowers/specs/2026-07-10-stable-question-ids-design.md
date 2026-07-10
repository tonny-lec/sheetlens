# SheetLens 安定質問 ID と旧 ID 自動移行 設計書

## 目的

質問の走査順に依存する `q-NNN` を、質問の意味と内容から決定的に生成する stable ID へ
置き換える。既存 annotation の `questions_answered` は書き換えず、プロジェクト直下の
機械可読 catalog で旧連番を自動解決する。

前方へシート、非表示属性、入力規則などを追加しても、既存質問への回答が別質問へ
静かに移らないことを最重要条件とする。

## 現状と根本原因

`generate_questions()` は質問を追加するたびに `len(qs) + 1` を使って `q-NNN` を付ける。
このため workbook の走査順の前方へ質問が追加されると、後続する全質問の ID が変わる。

annotation は回答済み ID の文字列だけを保持し、`compile` と `check` は現在生成した ID との
単純な集合照合しか行わない。旧 `q-001` が新しい別質問の `q-001` と一致すると、stale として
検出されず、別質問が回答済みとして扱われる。

さらに `sheet/category/target` だけでは一意にならない。hidden かつ protected のシートでは、
同じ `sheet`、`hidden_reason`、シート名 target を持つ別質問が生成される。そのため生成規則を
identity の一部にする。

## 設計原則

- stable ID と legacy alias を明確に分離する。
- annotation YAML は人間の蓄積資産として一切書き換えない。
- legacy alias は一度確定したら、後続の再抽出で別質問へ付け替えない。
- 自動移行の根拠を確認できない場合は推測せず、未解決として警告する。
- `check` は読み取り専用を維持する。
- 同じ入力から同じ ID と catalog を生成し、タイムスタンプや乱数を含めない。

## Stable ID

### 形式

新 ID は次の形式とする。

```text
q2-<rule>-<content digest の先頭 16 hex>
```

`q2-` prefix により、旧形式 `^q-[0-9]{3,}$` と機械的に区別できる。現行の `:03d` は
最小幅指定なので、1000 件目以降の旧 ID も legacy として扱う。digest は Python の
`hash()` ではなく SHA-256 を使う。省略部分が既存の別 full digest と衝突した場合は、同じ ID を
共有せず生成エラーにする。

### Identity と content

identity は次の canonical JSON から SHA-256 を生成する。

```text
rule, sheet, category, target
```

content digest は identity の canonical fields と正規化した質問文 `text` から生成する。
stable ID は content digest を含むため、質問の意味内容が変わると新 ID になる。一方、前方に
別質問が追加されても canonical fields が同じ既存質問の ID は変わらない。

`rule` は生成箇所を区別する固定の ASCII 識別子とする。少なくとも次を分ける。

- `sheet_role`
- `hidden_sheet`
- `protected_sheet`
- `hidden_columns`
- `input_region`
- `list_validation`
- `conditional_format`
- `button_macro`
- `vba_event`

同一生成内で identity が同じ質問が複数ある場合、正規化後の content も同一なら 1 件へ
重複排除する。content が異なる場合は rule の識別力不足なので生成エラーにする。ordinal は
前方追加で変化するため identity には使わない。

### 正規化

canonical fields と text は値の種類ごとに次の規則で正規化する。

- 全文字列の Unicode は NFC に統一する。
- `sheet` は workbook 内の名前をそのまま identity とし、意味を持ち得る空白を削除・圧縮しない。
- `target` は generator が生成する canonical 表記を使う。複数値のカンマ前後だけを除去し、
  セル range、macro 名、module 名の内部空白は変更しない。
- `text` は前後の空白を除去し、連続する空白文字を単一の半角スペースへ統一する。
- 複数 range の並び順は意味の一部として保持し、sort しない。
- `category` と `rule` は定義済み ASCII 値をそのまま使う。

正規化規則は golden test で固定し、規則変更を ID migration として扱えるようにする。

## Question ID Catalog

### 配置

catalog は SheetLens プロジェクト直下の `question-ids.json` に置く。`structure/` は再抽出で
削除され、`annotations/` は人間だけが編集するため、どちらにも配置しない。

### Schema

```json
{
  "schema_version": 1,
  "generator_version": 2,
  "source_sha256": "...",
  "legacy_source_sha256": "...",
  "current_ids": ["q2-sheet_role-a1b2c3d4e5f60708"],
  "questions": {
    "q2-sheet_role-a1b2c3d4e5f60708": {
      "rule": "sheet_role",
      "sheet": "入力",
      "category": "sheet_role",
      "target": "入力",
      "text": "...",
      "identity_sha256": "...",
      "content_sha256": "..."
    }
  },
  "legacy_aliases": {
    "q-001": "q2-sheet_role-a1b2c3d4e5f60708"
  },
  "unresolved_legacy_ids": []
}
```

`questions` は過去エントリも保持し、`current_ids` のみを現在有効な質問として扱う。
これにより annotation が参照する過去 ID を、内容変更と削除に分類できる。

`source_sha256` は `structure/raw.json` の `Workbook.sha256`、すなわち抽出元 Excel の bytes に
対する SHA-256 とする。`generator_version` は canonicalization と質問生成規則の世代を示し、
対応していない version は自動解決しない。`legacy_source_sha256` は legacy alias を初めて
確定した旧 `Workbook.sha256` とし、再抽出後も変更しない。legacy ID を自動解決した通知では
この hash を由来として示し、回答時世代そのものを証明する値ではないことを明記する。

JSON object の出力順、配列順、indent、末尾 newline を固定し、同じ状態から byte-for-byte で
同じ catalog を生成する。

catalog load/build 時は、各 entry の canonical fields から identity/content digest と短縮 ID を
再計算する。さらに current catalog は同じ raw.json から新たに生成した question set と完全一致
することを検証する。source hash だけが一致する stale または改変 catalog は利用しない。

## Legacy 自動移行

### 初回移行

既存 catalog がないプロジェクトでは、既存 `structure/raw.json` から生成規則順の question
candidate 列を作る。各 candidate に旧走査位置の `q-NNN` と新 stable ID の両方を付けることで、
各旧 ID を対応する stable ID へ割り当てる。完全重複 candidate を最終質問一覧で 1 件へまとめる
場合も、複数の旧 ID を同じ stable ID へ alias できるため、走査位置と対応がずれない。

既存 `questions.md` は移行元ではなく、現在の legacy snapshot の整合性 guard として使う。
旧 generator と renderer で `questions.md` 全体を再描画し、checkbox の `[ ]` / `[x]` だけを
同一表現へ正規化した bytes が既存ファイルと完全一致する場合だけ alias を確定する。field 単位の
Markdown parse は行わない。

`questions.md` がない、再描画結果と一致しない、または未知の行がある場合は alias を推測しない。
annotation 内の旧 ID を `unresolved_legacy_ids` に残し、手動確認が必要な警告を出す。

この guard が証明するのは、既存 raw.json と questions.md が同じ現在 snapshot を表すことまでで
あり、annotation がその snapshot に回答したことではない。stable ID 導入前に旧版 SheetLens で
再抽出し、既に旧 ID が別質問へ静かに移っていた場合、回答時世代を復元する情報は存在しない。
通常の初回アップグレードでは自動移行するが、移行時にこの制約を明示し、過去に失われた世代を
安全に復元できるとは扱わない。

### Catalog の継承

一度保存した `legacy_aliases` は再計算しない。再抽出時は `structure/` を削除する前に catalog と
旧 raw.json を読み、新 workbook の current questions と merge する。既存 `questions` と alias を
保持し、`current_ids` と `source_sha256` だけを新世代へ進める。

catalog の単一ファイル更新は、一時ファイルを同じディレクトリへ書き、`Path.replace()` で
置換する。プロジェクト全体のトランザクション化は SL-013 の範囲とし、本課題では扱わない。

## 回答 ID の解決

共通 resolver が annotation の各 ID を次のいずれかへ分類する。

1. `current`: 現在の stable ID と直接一致する。
2. `legacy`: legacy alias が指す stable ID が現在も有効である。
3. `changed`: 過去 ID と同じ identity の current question があり、content が変わった。
4. `deleted`: catalog に過去 ID はあるが、同じ identity の current question がない。
5. `unresolved`: 未知 ID、確定できない legacy ID、または曖昧な対応である。

renderer へ渡す回答済み集合には `current` と `legacy` の解決後 stable ID だけを含める。
`changed`、`deleted`、`unresolved` は未回答として扱い、別質問を回答済みにしない。

## Command ごとの動作

### extract

1. 既存 catalog と旧 raw.json を、`structure/` の削除前に読む。
2. catalog がなければ、安全条件を満たす legacy alias を作る。
3. 新 workbook を解析し、stable questions を生成する。
4. history と alias を保持して current questions を merge し、完全性を検証する。
5. ここまでの処理がすべて成功した後にだけ旧 `structure/` を削除する。
6. 構造ビュー、`questions.md`、`question-ids.json` を生成する。

annotation YAML の byte sequence は変更しない。移行不能な旧 ID があっても annotation を
保持して抽出を継続し、警告可能な状態を catalog に残す。

### compile

stable questions と catalog を読み、共通 resolver で回答済み stable ID を作って各 view を
再生成する。catalog のない既存プロジェクトでは、安全条件を満たした初回 catalog を保存する。
解決した legacy ID の件数を通知するが、annotation YAML は変更しない。

### check

compile と同じ診断を行うが、catalog を作成・更新しない。catalog がなければメモリ上だけで
初回移行を評価する。通常の stale 警告は終了コード 0 を維持する。

compile は resolver が検出した未解決 legacy ID を catalog へ追記する。check は同じ追記結果を
メモリ上の診断にだけ使い、ファイルへ保存しない。

## エラーと警告

- 一意に解決した旧 ID: 回答済みとして扱い、`compile` で自動移行件数を通知する。
- 内容変更: `警告（質問ID変更）` として旧 ID と現在の ID を示す。
- 削除: `警告（質問ID削除）` として annotation に残る ID を示す。
- 未知または移行不能: `警告（質問ID未解決）` として報告する。
- identity に異なる current content が複数ある: 質問生成エラーとして終了コード 1。
- digest 衝突、catalog 破損、未知 schema version: catalog エラーとして終了コード 1。
- catalog と raw.json の source hash 不一致: `extract`、`compile`、`check` は終了コード 1。

`extract` は既存 catalog を先に読めない場合、旧 alias を失う可能性があるため、既存出力を
削除する前に終了する。catalog が読めても旧 raw の `Workbook.sha256` と一致しない場合は、
alias の由来を保証できないため同じく削除前に終了し、resolver でも alias を利用しない。

## 変更範囲

- `src/sheetlens/detectors/questions.py`: rule-aware な stable question 生成と重複検査。
- `src/sheetlens/question_ids.py`: catalog schema、load/save/merge、legacy migration、resolver。
- `src/sheetlens/pipeline.py`: extract/compile と catalog lifecycle の統合。
- `src/sheetlens/cli.py`: check 診断と catalog error の表示。
- `src/sheetlens/renderers/markdown.py`: catalog の説明と stable ID 表示文言。
- `README.md`: 出力構成と stable/legacy ID の説明。
- `tests/test_questions.py`: stable ID、正規化、前方追加、重複の単体テスト。
- `tests/test_question_ids.py`: catalog と resolver の単体テスト。
- `tests/test_extract_e2e.py`: 再抽出と catalog 継承。
- `tests/test_compile_e2e.py`: legacy 自動解決と YAML 非変更。
- `tests/test_check_e2e.py`: changed/deleted/unresolved と read-only 性。
- `tests/test_markdown.py`: 生成 README の catalog 説明。

## テスト方針

実装は test-driven-development で進め、各 production change の前に失敗テストを確認する。

### Stable ID

- 既知の質問に対する exact ID を golden value として固定する。
- 前方へのシート、hidden 属性、入力規則の追加後も既存 ID が変わらない。
- Unicode、連続空白、カンマ周辺空白の正規化を固定する。
- legacy 判定の 999 件目と 1000 件目の境界を固定する。
- hidden と protected が別 identity になる。
- 完全重複は 1 件になり、異なる content の identity 重複と digest 衝突は失敗する。

### Catalog と resolver

- catalog の schema、決定的 JSON、単一ファイルの atomic replace。
- legacy alias の初回生成と、再抽出後に alias が付け替わらないこと。
- current、legacy、changed、deleted、unresolved の分類。
- history merge、破損 JSON、未知 schema、source hash 不一致。

### E2E

- 既存 `q-001` が YAML 無変更で正しい stable 質問を回答済みにする。
- 前方へ質問を追加して再抽出しても旧回答が別質問へ移らない。
- 旧 questions.md と raw.json が不一致なら alias を作らない。
- 既に旧版で再抽出された世代は自動復元できないという移行警告を表示する。
- `check` が内容変更、削除、未解決 ID を報告する。
- `check` が catalog を作成または更新しない。
- 移行前後で annotation YAML の byte sequence が同一である。

実装完了時は関連テスト、全 pytest、ruff、project-state validator を実行する。

## 対象外

- annotation ID と annotation ファイルの `sheet` の対応検証
- annotation schema の刷新または回答 fingerprint field の追加
- annotation YAML の自動書き換え
- 質問文の全面的な変更、新しい質問カテゴリの追加
- プロジェクト全体のアトミックな extract/compile
- stable ID 導入前に既に失われた annotation 回答時世代の復元
