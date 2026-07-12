---
id: SL-027
title: Workbook 読込リソースの確実な解放
status: proposed
priority: P2
type: defect
milestone: M2
depends_on: []
touches:
  - src/sheetlens/reader/workbook.py
  - tests/test_reader.py
  - tests/test_xlsm_e2e.py
owner: null
---

# SL-027 Workbook 読込リソースの確実な解放

## 背景と根本原因

`read_workbook()` は数式用と cached value 用に二つの openpyxl Workbook を開き、XLSM では `keep_vba=True` の archive も保持するが、正常系・例外系の close を保証していない。単発実行では表面化しにくいが、反復処理でファイルハンドル残留や unraisable warning につながる。

## 根拠

`src/sheetlens/reader/workbook.py` は `openpyxl.load_workbook()` を二度呼び出した後に Workbook を閉じていない。現行の XLSM E2E 後に `zipfile.ZipFile.__del__` の `I/O operation on closed file` warning が発生し、`keep_vba=True` の `vba_archive` が解放されないことを確認した。

## 受け入れ条件

- [ ] 正常系と各読込・抽出例外系で、`wb_f`、`wb_v`、XLSM の `vba_archive` を確実に close する。
- [ ] XLSX と XLSM の反復読込で unraisable warning とファイルハンドル残留がない。
- [ ] Windows を含め、抽出直後に入力ファイルを移動・削除できることを回帰テストで確認する。
- [ ] close 処理が抽出結果、VBA 内容、既存エラー分類を変えない。

## 対象外

openpyxl や oletools 自体の内部 archive 実装の変更、入力ファイルの暗号化解除。

## 実装計画

着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。

## 完了証拠

完了時に正常・例外・XLSM反復処理、warning、Windows受け入れ結果を記録する。
