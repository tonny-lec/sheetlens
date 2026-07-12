# openpyxl-vba-test.xlsm — SheetLens 抽出結果

**⚠ この抽出には 3 件の欠落があります:**

- Scratch: drawing xl/drawings/drawing1.xml の AlternateContent は未対応です
- Scratch: VML drawing は未対応です
- Scratch: ActiveX control 2件の詳細抽出は未対応です

## 読み方

- `structure/sheet-*.md`: シートごとの構造ビュー（compile 後は業務注釈も織り込み済み）
- `structure/raw.json`: 省略なしの全抽出データ（機械可読の正）
- `structure/vba/*.bas`: VBA ソース
- `annotations/*.yaml`: 業務上の意味（人間の回答。手で編集してよい唯一の場所）
- `questions.md`: 業務担当者に確認すべき質問リスト
- `question-ids.json`: 安定した質問 ID と旧 ID alias の履歴

## 質問 ID と注釈

- 現在の質問 ID は内容から決定的に生成する `q2-<rule>-<16hex>` 形式です。
- 旧形式の `q-NNN` は `question-ids.json` の alias で引き続き解決し、alias は一度保存した対応先から変更しません。
- SheetLens は質問 ID を含む `annotations/*.yaml` を書き換えません。
- `legacy_source_sha256` は alias を作ったアップグレード前の抽出 snapshot の由来を示す文脈情報であり、暗号学的な完全性や回答時点を証明するものではありません。
- `question-ids.json` を手で編集しないでください。alias を別の有効な過去/現行 ID へ意図的に付け替えた場合、SheetLens はその改ざんを検出できません。

## シート一覧

- Scratch: 内容範囲 なし / 構造範囲 なし

## 未確認事項: 3 件（`questions.md` 参照）
