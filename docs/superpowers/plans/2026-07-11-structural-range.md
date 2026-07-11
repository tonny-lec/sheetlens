# SL-009 structural range と非表示範囲の修正 実装計画

## 目的

値・数式セルが占める content range と、結合・入力規則・条件付き書式を含む
structural range を分離する。空の構造要素だけを持つシートでも構造範囲を失わず、
グループ化された非表示列を全列分保持する。

## 設計

- `Sheet` に `content_range` と `structural_range` を追加する。
- `used_range` は既存利用者向けの互換フィールドとして `content_range` と同期する。
  旧入力・新入力の片方だけなら補完し、両方が競合する入力は拒否する。
- content range は抽出した値・数式セルの座標だけから境界矩形を求める。
- structural range は content range、結合範囲、worksheet 上の生の入力規則範囲、
  worksheet 上の生の条件付き書式範囲を包含する有限の境界矩形とする。
- 全列・全行指定は Excel の最大行・最大列までの境界として扱い、セルを列挙しない。
- 範囲の解釈に失敗した場合は黙って落とさず `extraction_gaps` に記録する。
- 非表示列 dimension の `min` / `max` を展開し、重複排除して列番号順に保存する。
- Markdown のセルグリッドは content range を使い、structural range による空セル走査を避ける。
- 注釈の存在範囲検証は structural range を優先し、旧 IR は content/used range に
  フォールバックする。

## 実装手順

1. IR の互換性、範囲算出、構造だけのシート、抽出失敗、非表示列展開を表す失敗テストを追加する。
2. `Sheet` の範囲フィールドと旧新入力の互換検証を実装する。
3. reader に境界矩形計算と生の構造範囲収集、非表示列展開を実装する。
4. machine manifest、Markdown、注釈検証を新しい範囲の意味に接続する。
5. hidden-column 質問 target と出力互換性の回帰テストを追加する。
6. 対象テスト、全テスト、Ruff、project-state check、diff check を実行する。
7. 問題探索型レビューと Advisor の完了前レビューを反映し、課題証拠を更新する。

## 検証

```text
uv run pytest tests/test_ir.py tests/test_reader.py tests/test_machine.py tests/test_markdown.py tests/test_annotations.py tests/test_questions.py -q
uv run pytest -q
uv run ruff check .
uv run python scripts/check_project_state.py check
git diff --check
```
