# SheetLens v1 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 業務 Excel（.xlsx/.xlsm）を AI エージェントが誤読しない中間表現（Markdown + JSON + 注釈 YAML）に変換する CLI `sheetlens` を作る。

**Architecture:** 決定的パイプライン `reader（openpyxl/oletools → pydantic IR）→ detectors（領域・数式パターン・質問生成）→ renderers（Markdown/JSON）`。構造層（再生成可能）と意味層（annotations/、人間の回答、絶対に消さない）を分離。SheetLens 自体は LLM を呼ばない。

**Tech Stack:** Python 3.12+ / uv / openpyxl / oletools / pydantic v2 / pyyaml / typer / pytest / ruff

**設計書:** `docs/superpowers/specs/2026-07-07-sheetlens-design.md`（承認済み。判断に迷ったらこちらが正）

## Global Constraints

- Python `>=3.12`、uv 管理、src レイアウト（`src/sheetlens/`）。
- 依存は openpyxl / oletools / pydantic / pyyaml / typer のみ。dev は pytest / ruff のみ。新規依存の追加禁止。
- **出力は入力に対して決定的**: タイムスタンプ・乱数・環境依存の値を成果物に入れない（ゴールデンテストの前提）。
- **SheetLens は LLM を呼ばない。**
- **annotations/ 配下を書き換え・削除するコードを書かない**（読み取り専用。書くのは人間と AI エージェント）。
- **静かな欠落の禁止**: 抽出に失敗した要素は例外で握りつぶさず `Workbook.extraction_gaps` に記録する。
- 成果物ドキュメント（Markdown）の言語は日本語。
- テストの Excel フィクスチャはコミットせず、テストコード内で openpyxl により生成する（tmp_path 使用）。
- 作業ブランチ: `feat/v1`（Task 1 で `feat/design-spec` から作成）。`main` に直接コミットしない。
- コミットメッセージ末尾に `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` を付ける。
- openpyxl の注意: `data_only=True` のキャッシュ値は「Excel で保存されたことのないファイル」では None になる。テストでは数式セルの value が None であることを前提にする。

---

### Task 1: プロジェクト scaffold と CLI スケルトン

**Files:**
- Create: `pyproject.toml`
- Create: `src/sheetlens/__init__.py`
- Create: `src/sheetlens/cli.py`
- Create: `tests/test_cli.py`
- Modify: `CLAUDE.md`（コマンド節の追記）

**Interfaces:**
- Produces: typer アプリ `sheetlens.cli:app`。コマンド `extract` / `compile` / `check`（この時点では未実装メッセージを出すだけのスタブ）。

- [ ] **Step 1: ブランチ作成**

```bash
git checkout -b feat/v1
```

- [ ] **Step 2: pyproject.toml を作成**

```toml
[project]
name = "sheetlens"
version = "0.1.0"
description = "AI エージェントのための Excel 理解支援ツール"
requires-python = ">=3.12"
dependencies = [
    "openpyxl>=3.1",
    "oletools>=0.60",
    "pydantic>=2.7",
    "pyyaml>=6.0",
    "typer>=0.12",
]

[project.scripts]
sheetlens = "sheetlens.cli:app"

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.4"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/sheetlens"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

- [ ] **Step 3: 失敗するテストを書く**

`tests/test_cli.py`:

```python
from typer.testing import CliRunner

from sheetlens.cli import app

runner = CliRunner()


def test_help_lists_three_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("extract", "compile", "check"):
        assert cmd in result.output
```

- [ ] **Step 4: テストが失敗することを確認**

Run: `uv sync && uv run pytest tests/test_cli.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'sheetlens'` など）

- [ ] **Step 5: 最小実装**

`src/sheetlens/__init__.py` は空ファイル。`src/sheetlens/cli.py`:

```python
from pathlib import Path

import typer

app = typer.Typer(help="業務 Excel を AI が誤読しない中間表現に変換する", no_args_is_help=True)


@app.command()
def extract(file: Path, out: Path | None = typer.Option(None, "-o", "--out")) -> None:
    """xlsx/xlsm から構造層と questions.md を生成する。"""
    typer.echo("extract: 未実装")
    raise typer.Exit(1)


@app.command(name="compile")
def compile_cmd(project: Path) -> None:
    """構造層 + 注釈を統合した Markdown を再生成する。"""
    typer.echo("compile: 未実装")
    raise typer.Exit(1)


@app.command()
def check(project: Path) -> None:
    """孤立注釈・未回答質問・スキーマ違反を報告する。"""
    typer.echo("check: 未実装")
    raise typer.Exit(1)
```

- [ ] **Step 6: テストが通ることを確認**

Run: `uv run pytest tests/test_cli.py -v && uv run ruff check .`
Expected: PASS / ruff エラーなし

- [ ] **Step 7: CLAUDE.md のコマンド節を追記**

CLAUDE.md の「## このファイルの更新義務」節を以下で**置き換える**:

```markdown
## コマンド

- 依存同期: `uv sync`
- テスト全件: `uv run pytest` / 単一ファイル: `uv run pytest tests/test_reader.py -v` /
  単一テスト: `uv run pytest tests/test_reader.py::test_name -v`
- Lint: `uv run ruff check .`
- 実行例: `uv run sheetlens extract <file.xlsx>` → `<file>.sheetlens/` を生成
```

- [ ] **Step 8: コミット**

```bash
git add pyproject.toml uv.lock src tests CLAUDE.md
git commit -m "feat: プロジェクト scaffold と CLI スケルトン"
```

---

### Task 2: 中間表現（IR）データモデル

**Files:**
- Create: `src/sheetlens/model/__init__.py`（空）
- Create: `src/sheetlens/model/ir.py`
- Test: `tests/test_ir.py`

**Interfaces:**
- Produces: `sheetlens.model.ir` の pydantic モデル群。以降の全タスクがこれを使う。
  `Cell(ref, value, formula)` / `ValidationRule(ranges, type, formula1, choices)` /
  `ConditionalFormat(range, rule_type, operator, formula, stop_if_true)` /
  `VbaModule(name, code)` / `ButtonLink(sheet, label, macro)` /
  `Sheet(name, used_range, hidden, protected, hidden_cols, hidden_rows, cells, merged, validations, conditional_formats)` /
  `Workbook(source_file, sha256, sheets, vba_modules, buttons, defined_names, external_refs, extraction_gaps)`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_ir.py`:

```python
from sheetlens.model import ir


def test_workbook_json_roundtrip():
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="見積入力",
                used_range="A1:C3",
                cells=[ir.Cell(ref="A1", value="見積書"), ir.Cell(ref="C3", formula="=A1*2")],
                merged=["A1:B1"],
                validations=[
                    ir.ValidationRule(ranges=["C5"], type="list", formula1='"通常,特急"', choices=["通常", "特急"])
                ],
                conditional_formats=[
                    ir.ConditionalFormat(range="F1:F9", rule_type="cellIs", operator="lessThan", formula="0")
                ],
            )
        ],
        vba_modules=[ir.VbaModule(name="Module1", code="Sub X()\nEnd Sub")],
        buttons=[ir.ButtonLink(sheet="見積入力", macro="Module1.X")],
        extraction_gaps=["dummy gap"],
    )
    restored = ir.Workbook.model_validate_json(wb.model_dump_json())
    assert restored == wb
    assert restored.sheets[0].cells[1].formula == "=A1*2"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_ir.py -v`
Expected: FAIL（`ModuleNotFoundError: sheetlens.model`）

- [ ] **Step 3: 実装**

`src/sheetlens/model/ir.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field

Primitive = str | int | float | bool | None


class Cell(BaseModel):
    ref: str
    value: Primitive = None
    formula: str | None = None


class ValidationRule(BaseModel):
    ranges: list[str]
    type: str
    formula1: str | None = None
    choices: list[str] = Field(default_factory=list)


class ConditionalFormat(BaseModel):
    range: str
    rule_type: str
    operator: str | None = None
    formula: str | None = None
    stop_if_true: bool = False


class VbaModule(BaseModel):
    name: str
    code: str


class ButtonLink(BaseModel):
    sheet: str
    label: str | None = None
    macro: str


class Sheet(BaseModel):
    name: str
    used_range: str | None = None
    hidden: bool = False
    protected: bool = False
    hidden_cols: list[str] = Field(default_factory=list)
    hidden_rows: list[int] = Field(default_factory=list)
    cells: list[Cell] = Field(default_factory=list)
    merged: list[str] = Field(default_factory=list)
    validations: list[ValidationRule] = Field(default_factory=list)
    conditional_formats: list[ConditionalFormat] = Field(default_factory=list)


class Workbook(BaseModel):
    source_file: str
    sha256: str
    sheets: list[Sheet] = Field(default_factory=list)
    vba_modules: list[VbaModule] = Field(default_factory=list)
    buttons: list[ButtonLink] = Field(default_factory=list)
    defined_names: dict[str, str] = Field(default_factory=dict)
    external_refs: list[str] = Field(default_factory=list)
    extraction_gaps: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_ir.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add src/sheetlens/model tests/test_ir.py
git commit -m "feat: 中間表現の pydantic データモデル"
```

---

### Task 3: reader — セル・数式・結合・シート属性の抽出

**Files:**
- Create: `src/sheetlens/reader/__init__.py`（空）
- Create: `src/sheetlens/reader/workbook.py`
- Create: `tests/conftest.py`
- Test: `tests/test_reader.py`

**Interfaces:**
- Consumes: `sheetlens.model.ir`
- Produces: `read_workbook(path: Path) -> ir.Workbook`（この時点では validations / conditional_formats / vba / buttons は空。Task 4/5 で拡張）
- Produces (テスト用): conftest の fixture `make_xlsx(builder, name="test.xlsx") -> Path`

- [ ] **Step 1: conftest を書く**

`tests/conftest.py`:

```python
from collections.abc import Callable
from pathlib import Path

import openpyxl
import pytest


@pytest.fixture
def make_xlsx(tmp_path: Path) -> Callable:
    """openpyxl の Workbook を builder で構築して保存し、パスを返す。"""

    def _make(builder: Callable[[openpyxl.Workbook], None], name: str = "test.xlsx") -> Path:
        wb = openpyxl.Workbook()
        builder(wb)
        path = tmp_path / name
        wb.save(path)
        return path

    return _make
```

- [ ] **Step 2: 失敗するテストを書く**

`tests/test_reader.py`:

```python
from sheetlens.reader.workbook import read_workbook


def _build(wb):
    ws = wb.active
    ws.title = "見積入力"
    ws["A1"] = "見積書"
    ws.merge_cells("A1:C1")
    ws["A3"] = "数量"
    ws["B3"] = 5
    ws["C3"] = "=B3*100"
    ws.column_dimensions["D"].hidden = True
    hidden = wb.create_sheet("計算用")
    hidden["A1"] = 1
    hidden.sheet_state = "hidden"


def test_read_cells_formulas_merges(make_xlsx):
    wb = read_workbook(make_xlsx(_build))
    assert wb.source_file == "test.xlsx"
    assert len(wb.sha256) == 64
    sheet = wb.sheets[0]
    assert sheet.name == "見積入力"
    assert "A1:C1" in sheet.merged
    cells = {c.ref: c for c in sheet.cells}
    assert cells["A1"].value == "見積書"
    assert cells["B3"].value == 5
    assert cells["C3"].formula == "=B3*100"
    assert "D" in sheet.hidden_cols
    assert wb.sheets[1].hidden is True
```

- [ ] **Step 3: テストが失敗することを確認**

Run: `uv run pytest tests/test_reader.py -v`
Expected: FAIL（`ModuleNotFoundError: sheetlens.reader`）

- [ ] **Step 4: 実装**

`src/sheetlens/reader/workbook.py`:

```python
import hashlib
from pathlib import Path

import openpyxl

from sheetlens.model import ir


def _coerce(value: object) -> ir.Primitive:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)  # datetime 等は文字列化


def read_workbook(path: Path) -> ir.Workbook:
    data = path.read_bytes()
    keep_vba = path.suffix.lower() in (".xlsm", ".xltm")
    wb_f = openpyxl.load_workbook(path, data_only=False, keep_vba=keep_vba)
    wb_v = openpyxl.load_workbook(path, data_only=True)
    gaps: list[str] = []
    sheets: list[ir.Sheet] = []
    for ws_f in wb_f.worksheets:
        ws_v = wb_v[ws_f.title]
        cells: list[ir.Cell] = []
        for row in ws_f.iter_rows():
            for c in row:
                if c.value is None:
                    continue
                if c.data_type == "f":
                    raw = c.value
                    formula = raw if isinstance(raw, str) else str(getattr(raw, "text", raw))
                    cells.append(
                        ir.Cell(ref=c.coordinate, value=_coerce(ws_v[c.coordinate].value), formula=formula)
                    )
                else:
                    cells.append(ir.Cell(ref=c.coordinate, value=_coerce(c.value)))
        sheets.append(
            ir.Sheet(
                name=ws_f.title,
                used_range=ws_f.calculate_dimension() if cells else None,
                hidden=ws_f.sheet_state != "visible",
                protected=bool(ws_f.protection.sheet),
                hidden_cols=sorted(k for k, v in ws_f.column_dimensions.items() if v.hidden),
                hidden_rows=sorted(k for k, v in ws_f.row_dimensions.items() if v.hidden),
                cells=cells,
                merged=[str(r) for r in ws_f.merged_cells.ranges],
            )
        )
    defined = {}
    for name, defn in wb_f.defined_names.items():
        defined[name] = defn.attr_text or ""
    return ir.Workbook(
        source_file=path.name,
        sha256=hashlib.sha256(data).hexdigest(),
        sheets=sheets,
        defined_names=defined,
        extraction_gaps=gaps,
    )
```

- [ ] **Step 5: テストが通ることを確認**

Run: `uv run pytest tests/test_reader.py -v`
Expected: PASS

- [ ] **Step 6: コミット**

```bash
git add src/sheetlens/reader tests/conftest.py tests/test_reader.py
git commit -m "feat: reader — セル・数式・結合・シート属性の抽出"
```

---

### Task 4: reader — 入力規則と条件付き書式

**Files:**
- Create: `src/sheetlens/reader/features.py`
- Modify: `src/sheetlens/reader/workbook.py`（features の呼び出しを統合）
- Test: `tests/test_features.py`

**Interfaces:**
- Produces: `read_validations(ws_f, wb_v) -> list[ir.ValidationRule]` / `read_conditional_formats(ws_f) -> list[ir.ConditionalFormat]`
- Modifies: `read_workbook` が Sheet.validations / Sheet.conditional_formats を埋める。失敗時は `extraction_gaps` に記録して継続（静かな欠落の禁止）。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_features.py`:

```python
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from sheetlens.reader.workbook import read_workbook


def _build(wb):
    ws = wb.active
    ws.title = "入力"
    master = wb.create_sheet("区分マスタ")
    for i, v in enumerate(["通常", "特急"], start=2):
        master[f"A{i}"] = v
    dv_inline = DataValidation(type="list", formula1='"はい,いいえ"')
    dv_inline.add("B2")
    ws.add_data_validation(dv_inline)
    dv_ref = DataValidation(type="list", formula1="=区分マスタ!$A$2:$A$3")
    dv_ref.add("C5")
    ws.add_data_validation(dv_ref)
    red = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    ws.conditional_formatting.add("F1:F9", CellIsRule(operator="lessThan", formula=["0"], fill=red))


def test_validations_and_conditional_formats(make_xlsx):
    sheet = read_workbook(make_xlsx(_build)).sheets[0]
    rules = {r.ranges[0]: r for r in sheet.validations}
    assert rules["B2"].choices == ["はい", "いいえ"]
    assert rules["C5"].choices == ["通常", "特急"]
    cf = sheet.conditional_formats[0]
    assert cf.range == "F1:F9"
    assert cf.rule_type == "cellIs"
    assert cf.operator == "lessThan"
    assert cf.formula == "0"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_features.py -v`
Expected: FAIL（validations が空）

- [ ] **Step 3: 実装**

`src/sheetlens/reader/features.py`:

```python
from sheetlens.model import ir


def _resolve_list(wb_v, current_sheet: str, formula: str) -> list[str]:
    """'=区分マスタ!$A$2:$A$3' 形式のリスト参照を実際の選択肢値に展開する。"""
    ref = formula.lstrip("=")
    if "!" in ref:
        sheet_part, ref = ref.rsplit("!", 1)
        sheet_part = sheet_part.strip("'")
    else:
        sheet_part = current_sheet
    try:
        ws = wb_v[sheet_part]
        found = ws[ref.replace("$", "")]
        rows = found if isinstance(found, tuple) else ((found,),)
        values: list[str] = []
        for row in rows:
            for c in row if isinstance(row, tuple) else (row,):
                if c.value is not None:
                    values.append(str(c.value))
        return values
    except (KeyError, ValueError):
        return []


def read_validations(ws_f, wb_v) -> list[ir.ValidationRule]:
    rules: list[ir.ValidationRule] = []
    for dv in ws_f.data_validations.dataValidation:
        f1 = dv.formula1
        choices: list[str] = []
        if dv.type == "list" and f1:
            if f1.startswith('"'):
                choices = [s.strip() for s in f1.strip('"').split(",")]
            else:
                choices = _resolve_list(wb_v, ws_f.title, f1)
        rules.append(
            ir.ValidationRule(
                ranges=[str(r) for r in dv.sqref.ranges], type=dv.type or "unknown", formula1=f1, choices=choices
            )
        )
    return rules


def read_conditional_formats(ws_f) -> list[ir.ConditionalFormat]:
    out: list[ir.ConditionalFormat] = []
    for fmt in ws_f.conditional_formatting:
        for rule in fmt.rules:
            formulas = list(getattr(rule, "formula", None) or [])
            out.append(
                ir.ConditionalFormat(
                    range=str(fmt.sqref),
                    rule_type=rule.type or "unknown",
                    operator=getattr(rule, "operator", None),
                    formula=formulas[0] if formulas else None,
                    stop_if_true=bool(rule.stopIfTrue),
                )
            )
    return out
```

`src/sheetlens/reader/workbook.py` の `read_workbook` 内、`sheets.append(...)` の直前に以下を挿入し、`ir.Sheet(...)` に `validations=validations, conditional_formats=cformats,` を追加する:

```python
        from sheetlens.reader.features import read_conditional_formats, read_validations

        try:
            validations = read_validations(ws_f, wb_v)
        except Exception as e:  # noqa: BLE001 — 欠落は gap として記録して継続
            validations = []
            gaps.append(f"{ws_f.title}: 入力規則の抽出に失敗 ({e})")
        try:
            cformats = read_conditional_formats(ws_f)
        except Exception as e:  # noqa: BLE001
            cformats = []
            gaps.append(f"{ws_f.title}: 条件付き書式の抽出に失敗 ({e})")
```

（import はファイル先頭に移すこと）

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_features.py tests/test_reader.py -v`
Expected: PASS（既存テストも回帰していないこと）

- [ ] **Step 5: コミット**

```bash
git add src/sheetlens/reader tests/test_features.py
git commit -m "feat: reader — 入力規則（選択肢展開）と条件付き書式"
```

---

### Task 5: reader — VBA 抽出とボタン↔マクロ対応

**Files:**
- Create: `src/sheetlens/reader/vba.py`
- Create: `src/sheetlens/reader/buttons.py`
- Modify: `src/sheetlens/reader/workbook.py`（統合）
- Test: `tests/test_vba.py`

**Interfaces:**
- Produces: `extract_vba(path: Path) -> list[ir.VbaModule]`（.xlsm 以外は空リスト）
- Produces: `extract_buttons(path: Path) -> list[ir.ButtonLink]`（VML の `<x:FmlaMacro>` を解析）
- Modifies: `read_workbook` が `vba_modules` / `buttons` を埋める。失敗は gap 記録。

**注記:** openpyxl で VBA 入り .xlsm をゼロから生成できないため、`extract_vba` の正常系は
VBA_Parser のモックでテストする。実 .xlsm での検証は Task 15 の実地検証手順に含まれる。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_vba.py`:

```python
import zipfile

from sheetlens.model import ir
from sheetlens.reader.buttons import extract_buttons
from sheetlens.reader.vba import extract_vba

WORKBOOK_XML = """<?xml version="1.0"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets><sheet name="見積入力" sheetId="1" r:id="rId1"/></sheets></workbook>"""

WORKBOOK_RELS = """<?xml version="1.0"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1"
  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
  Target="worksheets/sheet1.xml"/></Relationships>"""

SHEET_RELS = """<?xml version="1.0"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId2"
  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing"
  Target="../drawings/vmlDrawing1.vml"/></Relationships>"""

VML = """<xml xmlns:v="urn:schemas-microsoft-com:vml"
 xmlns:x="urn:schemas-microsoft-com:office:excel">
 <v:shape><x:ClientData ObjectType="Button">
 <x:FmlaMacro>Module1.RegisterEstimate</x:FmlaMacro>
 </x:ClientData></v:shape></xml>"""


def test_extract_buttons_from_vml(tmp_path):
    path = tmp_path / "btn.xlsm"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", WORKBOOK_XML)
        z.writestr("xl/_rels/workbook.xml.rels", WORKBOOK_RELS)
        z.writestr("xl/worksheets/sheet1.xml", "<worksheet/>")
        z.writestr("xl/worksheets/_rels/sheet1.xml.rels", SHEET_RELS)
        z.writestr("xl/drawings/vmlDrawing1.vml", VML)
    assert extract_buttons(path) == [ir.ButtonLink(sheet="見積入力", macro="Module1.RegisterEstimate")]


def test_extract_vba_skips_xlsx(make_xlsx):
    path = make_xlsx(lambda wb: None)
    assert extract_vba(path) == []


def test_extract_vba_with_mocked_parser(tmp_path, monkeypatch):
    class FakeParser:
        def __init__(self, _):
            pass

        def detect_vba_macros(self):
            return True

        def extract_macros(self):
            yield ("f", "s", "Module1.bas", "Sub RegisterEstimate()\nEnd Sub")

        def close(self):
            pass

    import sheetlens.reader.vba as vba_mod

    monkeypatch.setattr(vba_mod, "VBA_Parser", FakeParser)
    path = tmp_path / "macro.xlsm"
    path.write_bytes(b"dummy")
    mods = extract_vba(path)
    assert mods == [ir.VbaModule(name="Module1.bas", code="Sub RegisterEstimate()\nEnd Sub")]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_vba.py -v`
Expected: FAIL（モジュールなし）

- [ ] **Step 3: 実装**

`src/sheetlens/reader/vba.py`:

```python
from pathlib import Path

from oletools.olevba import VBA_Parser

from sheetlens.model import ir

_MACRO_SUFFIXES = (".xlsm", ".xltm")


def extract_vba(path: Path) -> list[ir.VbaModule]:
    if path.suffix.lower() not in _MACRO_SUFFIXES:
        return []
    parser = VBA_Parser(str(path))
    try:
        if not parser.detect_vba_macros():
            return []
        return [
            ir.VbaModule(name=Path(vba_filename).name, code=vba_code)
            for (_f, _s, vba_filename, vba_code) in parser.extract_macros()
        ]
    finally:
        parser.close()
```

`src/sheetlens/reader/buttons.py`:

```python
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from sheetlens.model import ir

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
_MACRO_RE = re.compile(r"<x:FmlaMacro>([^<]+)</x:FmlaMacro>")


def extract_buttons(path: Path) -> list[ir.ButtonLink]:
    out: list[ir.ButtonLink] = []
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "xl/workbook.xml" not in names or "xl/_rels/workbook.xml.rels" not in names:
            return out
        wb_root = ET.fromstring(z.read("xl/workbook.xml"))
        rels_root = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {rel.get("Id"): rel.get("Target") for rel in rels_root.iter(_REL)}
        for sh in wb_root.iter(f"{_MAIN}sheet"):
            target = rid_to_target.get(sh.get(_RID))
            if not target:
                continue
            sheet_path = posixpath.normpath(posixpath.join("xl", target))
            rels_path = posixpath.join(
                posixpath.dirname(sheet_path), "_rels", posixpath.basename(sheet_path) + ".rels"
            )
            if rels_path not in names:
                continue
            for rel in ET.fromstring(z.read(rels_path)).iter(_REL):
                if not (rel.get("Type") or "").endswith("/vmlDrawing"):
                    continue
                vml_path = posixpath.normpath(
                    posixpath.join(posixpath.dirname(sheet_path), rel.get("Target"))
                )
                if vml_path not in names:
                    continue
                for m in _MACRO_RE.finditer(z.read(vml_path).decode("utf-8", errors="replace")):
                    out.append(ir.ButtonLink(sheet=sh.get("name"), macro=m.group(1)))
    return out
```

`read_workbook` の return 直前に統合（import は先頭へ）:

```python
    vba_modules: list[ir.VbaModule] = []
    buttons: list[ir.ButtonLink] = []
    try:
        vba_modules = extract_vba(path)
    except Exception as e:  # noqa: BLE001
        gaps.append(f"VBA の抽出に失敗 ({e})")
    try:
        buttons = extract_buttons(path)
    except Exception as e:  # noqa: BLE001
        gaps.append(f"ボタン↔マクロ対応の抽出に失敗 ({e})")
```

（`ir.Workbook(...)` に `vba_modules=vba_modules, buttons=buttons,` を追加）

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_vba.py tests/test_reader.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add src/sheetlens/reader tests/test_vba.py
git commit -m "feat: reader — VBA ソース抽出とボタン↔マクロ対応（VML 解析）"
```

---

### Task 6: detectors — 数式パターン集約

**Files:**
- Create: `src/sheetlens/detectors/__init__.py`（空）
- Create: `src/sheetlens/detectors/util.py`
- Create: `src/sheetlens/detectors/formula_patterns.py`
- Test: `tests/test_formula_patterns.py`

**Interfaces:**
- Consumes: `ir.Sheet`
- Produces: `runs(sorted_ints: list[int]) -> list[tuple[int, int]]`（連続整数のランへ分割。regions でも使う）
- Produces: `FormulaPattern(ranges: list[str], pattern: str, example: str, exceptions: list[str])` /
  `aggregate_formulas(sheet: ir.Sheet) -> list[FormulaPattern]`
- 仕様: 列ごとに数式の行番号を `{row}` に正規化して多数派パターンを作る。多数派の行範囲**内**の逸脱セルは
  その FormulaPattern の `exceptions` に `"E15: =C15*D15*1.1"` 形式で記録（業務上の特例の発見に直結）。
  範囲外の少数派は独立の FormulaPattern とする。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_formula_patterns.py`:

```python
from sheetlens.detectors.formula_patterns import aggregate_formulas
from sheetlens.model import ir


def _sheet(cells):
    return ir.Sheet(name="s", cells=cells)


def test_uniform_column_collapses_to_one_pattern():
    cells = [ir.Cell(ref=f"E{r}", formula=f"=C{r}*D{r}") for r in range(11, 31)]
    pats = aggregate_formulas(_sheet(cells))
    assert len(pats) == 1
    assert pats[0].ranges == ["E11:E30"]
    assert pats[0].pattern == "=C{row}*D{row}"
    assert pats[0].example == "=C11*D11"
    assert pats[0].exceptions == []


def test_deviating_cell_inside_range_is_exception():
    cells = [ir.Cell(ref=f"E{r}", formula=f"=C{r}*D{r}") for r in range(11, 31) if r != 15]
    cells.append(ir.Cell(ref="E15", formula="=C15*D15*1.1"))
    pats = aggregate_formulas(_sheet(cells))
    assert len(pats) == 1
    assert pats[0].exceptions == ["E15: =C15*D15*1.1"]
    assert pats[0].ranges == ["E11:E14", "E16:E30"]


def test_absolute_refs_normalized():
    cells = [ir.Cell(ref=f"D{r}", formula=f"=VLOOKUP(B{r},単価マスタ!$A$2:$C$9,3,FALSE)") for r in (2, 3)]
    pats = aggregate_formulas(_sheet(cells))
    assert len(pats) == 1
    assert pats[0].pattern == "=VLOOKUP(B{row},単価マスタ!$A{row}:$C{row},3,FALSE)"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_formula_patterns.py -v`
Expected: FAIL（モジュールなし）

- [ ] **Step 3: 実装**

`src/sheetlens/detectors/util.py`:

```python
def runs(sorted_ints: list[int]) -> list[tuple[int, int]]:
    """ソート済み整数列を連続ラン (start, end) のリストに分割する。"""
    out: list[tuple[int, int]] = []
    start = prev = sorted_ints[0]
    for n in sorted_ints[1:]:
        if n == prev + 1:
            prev = n
            continue
        out.append((start, prev))
        start = prev = n
    out.append((start, prev))
    return out
```

`src/sheetlens/detectors/formula_patterns.py`:

```python
import re
from collections import defaultdict

from openpyxl.utils import coordinate_to_tuple, get_column_letter
from pydantic import BaseModel, Field

from sheetlens.detectors.util import runs
from sheetlens.model import ir

_ROW_RE = re.compile(r"(?<![A-Za-z0-9_$])(\$?[A-Z]{1,3})\$?\d+")


class FormulaPattern(BaseModel):
    ranges: list[str]
    pattern: str
    example: str
    exceptions: list[str] = Field(default_factory=list)


def _normalize(formula: str) -> str:
    return _ROW_RE.sub(lambda m: m.group(1) + "{row}", formula)


def aggregate_formulas(sheet: ir.Sheet) -> list[FormulaPattern]:
    by_col: dict[str, list[tuple[int, ir.Cell]]] = defaultdict(list)
    for cell in sheet.cells:
        if cell.formula is None:
            continue
        row, col = coordinate_to_tuple(cell.ref)
        by_col[get_column_letter(col)].append((row, cell))
    patterns: list[FormulaPattern] = []
    for col, items in sorted(by_col.items()):
        items.sort(key=lambda t: t[0])
        groups: dict[str, list[tuple[int, ir.Cell]]] = defaultdict(list)
        for row, cell in items:
            groups[_normalize(cell.formula)].append((row, cell))
        majority = max(groups, key=lambda k: len(groups[k]))
        main_rows = [r for r, _ in groups[majority]]
        main = FormulaPattern(
            ranges=[
                f"{col}{a}:{col}{b}" if a != b else f"{col}{a}" for a, b in runs(main_rows)
            ],
            pattern=majority,
            example=groups[majority][0][1].formula,
        )
        for norm, group in groups.items():
            if norm == majority:
                continue
            for row, cell in group:
                if main_rows[0] <= row <= main_rows[-1]:
                    main.exceptions.append(f"{cell.ref}: {cell.formula}")
                else:
                    patterns.append(FormulaPattern(ranges=[cell.ref], pattern=norm, example=cell.formula))
        patterns.append(main)
    return patterns
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_formula_patterns.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add src/sheetlens/detectors tests/test_formula_patterns.py
git commit -m "feat: detectors — 数式パターン集約（範囲+パターン+例外）"
```

---

### Task 7: detectors — 領域検出

**Files:**
- Create: `src/sheetlens/detectors/regions.py`
- Test: `tests/test_regions.py`

**Interfaces:**
- Consumes: `ir.Sheet`, `sheetlens.detectors.util.runs`
- Produces: `Region(range: str, kind: str)`（kind は `"table"` | `"block"`）/
  `detect_regions(sheet: ir.Sheet) -> list[Region]`
- 仕様（v1 ヒューリスティック）: 空行で区切られた連続非空行の帯を 1 領域とする。帯の先頭行が
  すべて「数式なしの文字列」かつ 2 セル以上、かつ帯が 3 行以上なら `table`（先頭行=ヘッダとみなす）、
  それ以外は `block`。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_regions.py`:

```python
from sheetlens.detectors.regions import detect_regions
from sheetlens.model import ir


def test_bands_split_by_blank_rows():
    # 行 1-3 が連続（空行なし）、行 4-9 が空、行 10-13 が連続 → 2 領域
    cells = [
        ir.Cell(ref="A1", value="見積書"),
        ir.Cell(ref="A2", value="宛先"),
        ir.Cell(ref="B3", value="顧客名"),
    ]
    cells += [ir.Cell(ref="A10", value="品名"), ir.Cell(ref="B10", value="数量")]
    for r in range(11, 14):
        cells += [ir.Cell(ref=f"A{r}", value=f"品{r}"), ir.Cell(ref=f"B{r}", formula=f"=A{r}")]
    regions = detect_regions(ir.Sheet(name="s", cells=cells))
    assert [r.range for r in regions] == ["A1:B3", "A10:B13"]
    assert [r.kind for r in regions] == ["block", "table"]


def test_empty_sheet():
    assert detect_regions(ir.Sheet(name="s")) == []
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_regions.py -v`
Expected: FAIL（モジュールなし）

- [ ] **Step 3: 実装**

`src/sheetlens/detectors/regions.py`:

```python
from collections import defaultdict

from openpyxl.utils import coordinate_to_tuple, get_column_letter
from pydantic import BaseModel

from sheetlens.detectors.util import runs
from sheetlens.model import ir


class Region(BaseModel):
    range: str
    kind: str  # "table" | "block"


def detect_regions(sheet: ir.Sheet) -> list[Region]:
    rows: dict[int, list[tuple[int, ir.Cell]]] = defaultdict(list)
    for cell in sheet.cells:
        r, c = coordinate_to_tuple(cell.ref)
        rows[r].append((c, cell))
    if not rows:
        return []
    regions: list[Region] = []
    for start, end in runs(sorted(rows)):
        cols = [c for r in range(start, end + 1) for c, _ in rows.get(r, [])]
        rng = f"{get_column_letter(min(cols))}{start}:{get_column_letter(max(cols))}{end}"
        head = [cell for _, cell in sorted(rows[start], key=lambda t: t[0])]
        is_table = (
            end - start + 1 >= 3
            and len(head) >= 2
            and all(isinstance(c.value, str) and c.formula is None for c in head)
        )
        regions.append(Region(range=rng, kind="table" if is_table else "block"))
    return regions
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_regions.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add src/sheetlens/detectors/regions.py tests/test_regions.py
git commit -m "feat: detectors — 空行区切りによる領域検出"
```

---

### Task 8: detectors — 質問生成

**Files:**
- Create: `src/sheetlens/detectors/questions.py`
- Test: `tests/test_questions.py`

**Interfaces:**
- Consumes: `ir.Workbook`, `Region`, `FormulaPattern`
- Produces: `Question(id: str, sheet: str, target: str, category: str, text: str)` /
  `generate_questions(wb: ir.Workbook, regions: dict[str, list[Region]], patterns: dict[str, list[FormulaPattern]]) -> list[Question]`
- 仕様（設計書の検出ルール表に対応）: category は
  `sheet_role`（全シート）/ `input_source`（数式を含まない領域）/ `dropdown_semantics`（type=list の入力規則）/
  `alert_action`（条件付き書式）/ `trigger_timing`（ボタン + VBA イベントプロシージャ）/
  `hidden_reason`（非表示・保護されたシート/列）。ID は出現順に `q-001` 形式。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_questions.py`:

```python
from sheetlens.detectors.questions import generate_questions
from sheetlens.detectors.regions import Region
from sheetlens.model import ir


def test_rules_produce_expected_categories():
    wb = ir.Workbook(
        source_file="a.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="入力",
                used_range="A1:F30",
                hidden_cols=["D"],
                cells=[ir.Cell(ref="A3", value="顧客名"), ir.Cell(ref="E11", formula="=C11*D11")],
                validations=[ir.ValidationRule(ranges=["C5"], type="list", choices=["通常", "特急"])],
                conditional_formats=[ir.ConditionalFormat(range="F11:F30", rule_type="cellIs", operator="lessThan", formula="0")],
            )
        ],
        vba_modules=[ir.VbaModule(name="Sheet1.cls", code="Private Sub Worksheet_Change(ByVal Target As Range)\nEnd Sub")],
        buttons=[ir.ButtonLink(sheet="入力", macro="Module1.Register")],
    )
    regions = {"入力": [Region(range="A3:B8", kind="block"), Region(range="A10:F30", kind="table")]}
    qs = generate_questions(wb, regions, {"入力": []})
    cats = {q.category for q in qs}
    assert cats == {"sheet_role", "input_source", "dropdown_semantics", "alert_action", "trigger_timing", "hidden_reason"}
    assert [q.id for q in qs] == [f"q-{i:03d}" for i in range(1, len(qs) + 1)]
    # A3:B8 は数式を含まないので input_source、A10:F30 は E11 の数式を含むので対象外
    targets = [q.target for q in qs if q.category == "input_source"]
    assert targets == ["A3:B8"]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_questions.py -v`
Expected: FAIL（モジュールなし）

- [ ] **Step 3: 実装**

`src/sheetlens/detectors/questions.py`:

```python
import re

from openpyxl.utils import coordinate_to_tuple, range_boundaries
from pydantic import BaseModel

from sheetlens.detectors.formula_patterns import FormulaPattern
from sheetlens.detectors.regions import Region
from sheetlens.model import ir

_EVENT_RE = re.compile(r"^\s*(?:Public\s+|Private\s+)?Sub\s+((?:Worksheet_|Workbook_)\w+)", re.M)


class Question(BaseModel):
    id: str
    sheet: str
    target: str
    category: str
    text: str


def _contains_formula(sheet: ir.Sheet, rng: str) -> bool:
    min_c, min_r, max_c, max_r = range_boundaries(rng)
    for cell in sheet.cells:
        if cell.formula is None:
            continue
        r, c = coordinate_to_tuple(cell.ref)
        if min_r <= r <= max_r and min_c <= c <= max_c:
            return True
    return False


def generate_questions(
    wb: ir.Workbook,
    regions: dict[str, list[Region]],
    patterns: dict[str, list[FormulaPattern]],
) -> list[Question]:
    qs: list[Question] = []

    def add(sheet: str, target: str, category: str, text: str) -> None:
        qs.append(Question(id=f"q-{len(qs) + 1:03d}", sheet=sheet, target=target, category=category, text=text))

    for sheet in wb.sheets:
        add(sheet.name, sheet.name, "sheet_role",
            f"シート「{sheet.name}」の役割は何ですか？業務フローのどの工程で使いますか？")
        if sheet.hidden:
            add(sheet.name, sheet.name, "hidden_reason", "このシートはなぜ非表示になっていますか？")
        if sheet.protected:
            add(sheet.name, sheet.name, "hidden_reason", "このシートはなぜ保護されていますか？")
        if sheet.hidden_cols:
            add(sheet.name, ",".join(sheet.hidden_cols), "hidden_reason",
                f"非表示の列（{', '.join(sheet.hidden_cols)}）には何が入っており、なぜ隠されていますか？")
        for region in regions.get(sheet.name, []):
            if not _contains_formula(sheet, region.range):
                add(sheet.name, region.range, "input_source",
                    f"範囲 {region.range} のデータは誰が・いつ・何を見て入力しますか？"
                    "（手入力 / 他システムからの貼り付け / VBA 自動入力）")
        for v in sheet.validations:
            if v.type != "list":
                continue
            label = "、".join(v.choices) if v.choices else (v.formula1 or "参照先リスト")
            add(sheet.name, ",".join(v.ranges), "dropdown_semantics",
                f"プルダウン（{', '.join(v.ranges)}）の選択肢「{label}」はそれぞれ業務上何を意味し、"
                "選択によって後続の処理・判断はどう変わりますか？")
        for cf in sheet.conditional_formats:
            add(sheet.name, cf.range, "alert_action",
                f"範囲 {cf.range} が条件付き書式で強調表示されたとき、業務担当者は何をしますか？")
    for b in wb.buttons:
        add(b.sheet, b.macro, "trigger_timing",
            f"ボタン（マクロ {b.macro}）はどの業務タイミングで押しますか？押す前提条件はありますか？")
    for m in wb.vba_modules:
        for ev in _EVENT_RE.findall(m.code):
            add("(VBA)", f"{m.name}.{ev}", "trigger_timing",
                f"イベントプロシージャ {ev} は業務上どんな操作で発火し、何を自動化していますか？")
    return qs
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_questions.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add src/sheetlens/detectors/questions.py tests/test_questions.py
git commit -m "feat: detectors — 構造からの質問リスト自動生成"
```

---

### Task 9: annotations — スキーマ・ローダ・孤立注釈チェック

**Files:**
- Create: `src/sheetlens/annotations/__init__.py`（空）
- Create: `src/sheetlens/annotations/schema.py`
- Test: `tests/test_annotations.py`

**Interfaces:**
- Consumes: `ir.Workbook`
- Produces: `AnnotationTarget(range, kind, value, by, when, values, note)` /
  `SheetAnnotations(sheet, role, workflow_stage, targets, questions_answered)` /
  `AnnotationError(Exception)` /
  `load_annotations(dir: Path) -> list[SheetAnnotations]`（YAML 破損・スキーマ違反はファイル名つき AnnotationError）/
  `find_orphans(wb: ir.Workbook, anns: list[SheetAnnotations]) -> list[str]`
- kind の固定語彙: `input_source` / `dropdown_semantics` / `trigger_timing` / `alert_action` / `sheet_role` / `free_note`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_annotations.py`:

```python
import pytest

from sheetlens.annotations.schema import AnnotationError, find_orphans, load_annotations
from sheetlens.model import ir

VALID_YAML = """\
sheet: 見積入力
role: "営業担当のメイン入力画面"
workflow_stage: "見積提示フェーズ"
targets:
  - range: A10:H30
    kind: input_source
    value: manual
    by: "営業担当"
  - range: C5
    kind: dropdown_semantics
    values:
      通常: "標準納期を適用"
      特急: "割増率を自動設定"
questions_answered: [q-001, q-004]
"""


def _wb():
    return ir.Workbook(
        source_file="a.xlsx", sha256="00" * 32,
        sheets=[ir.Sheet(name="見積入力", used_range="A1:H30")],
    )


def test_load_valid(tmp_path):
    (tmp_path / "見積入力.yaml").write_text(VALID_YAML, encoding="utf-8")
    anns = load_annotations(tmp_path)
    assert anns[0].sheet == "見積入力"
    assert anns[0].targets[1].values["特急"] == "割増率を自動設定"
    assert anns[0].questions_answered == ["q-001", "q-004"]


def test_invalid_kind_raises_with_filename(tmp_path):
    (tmp_path / "bad.yaml").write_text("sheet: s\ntargets:\n  - kind: unknown_kind\n", encoding="utf-8")
    with pytest.raises(AnnotationError, match="bad.yaml"):
        load_annotations(tmp_path)


def test_orphan_detection(tmp_path):
    (tmp_path / "見積入力.yaml").write_text(VALID_YAML, encoding="utf-8")
    (tmp_path / "消えたシート.yaml").write_text("sheet: 消えたシート\n", encoding="utf-8")
    wb = _wb()
    wb.sheets[0].used_range = "A1:F20"  # A10:H30 が範囲外になる
    orphans = find_orphans(wb, load_annotations(tmp_path))
    assert any("消えたシート" in o for o in orphans)
    assert any("A10:H30" in o for o in orphans)
    assert not any("C5" in o for o in orphans)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_annotations.py -v`
Expected: FAIL（モジュールなし）

- [ ] **Step 3: 実装**

`src/sheetlens/annotations/schema.py`:

```python
from pathlib import Path
from typing import Literal

import yaml
from openpyxl.utils import range_boundaries
from pydantic import BaseModel, Field, ValidationError

from sheetlens.model import ir


class AnnotationError(Exception):
    pass


class AnnotationTarget(BaseModel):
    range: str | None = None
    kind: Literal[
        "input_source", "dropdown_semantics", "trigger_timing",
        "alert_action", "sheet_role", "free_note",
    ]
    value: str | None = None
    by: str | None = None
    when: str | None = None
    values: dict[str, str] = Field(default_factory=dict)
    note: str | None = None


class SheetAnnotations(BaseModel):
    sheet: str
    role: str | None = None
    workflow_stage: str | None = None
    targets: list[AnnotationTarget] = Field(default_factory=list)
    questions_answered: list[str] = Field(default_factory=list)


def load_annotations(dir_path: Path) -> list[SheetAnnotations]:
    out: list[SheetAnnotations] = []
    for path in sorted(dir_path.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            out.append(SheetAnnotations.model_validate(data))
        except (yaml.YAMLError, ValidationError) as e:
            raise AnnotationError(f"{path.name}: {e}") from e
    return out


def find_orphans(wb: ir.Workbook, anns: list[SheetAnnotations]) -> list[str]:
    sheets = {s.name: s for s in wb.sheets}
    orphans: list[str] = []
    for ann in anns:
        sheet = sheets.get(ann.sheet)
        if sheet is None:
            orphans.append(f"{ann.sheet}: 注釈対象のシートが存在しません")
            continue
        for t in ann.targets:
            if not t.range:
                continue
            if not sheet.used_range:
                orphans.append(f"{ann.sheet}!{t.range}: シートが空です")
                continue
            u_min_c, u_min_r, u_max_c, u_max_r = range_boundaries(sheet.used_range)
            min_c, min_r, max_c, max_r = range_boundaries(t.range)
            if not (u_min_c <= min_c and u_min_r <= min_r and max_c <= u_max_c and max_r <= u_max_r):
                orphans.append(
                    f"{ann.sheet}!{t.range}: 現在の使用範囲 {sheet.used_range} の外にあります"
                )
    return orphans
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_annotations.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add src/sheetlens/annotations tests/test_annotations.py
git commit -m "feat: annotations — YAML スキーマ・ローダ・孤立注釈チェック"
```

---

### Task 10: renderers — manifest.json とシート間依存グラフ

**Files:**
- Create: `src/sheetlens/renderers/__init__.py`（空）
- Create: `src/sheetlens/renderers/machine.py`
- Test: `tests/test_machine.py`

**Interfaces:**
- Consumes: `ir.Workbook`
- Produces: `sheet_dependencies(wb) -> dict[str, list[str]]`（シート名 → 数式が参照する他シート名）/
  `external_references(wb) -> list[str]`（数式中の `[Book.xlsx]` 形式の外部ブック参照を収集。
  設計書どおり「記録のみ」で解決はしない）/
  `build_manifest(wb) -> dict`（source_file, sha256, sheets[{name, hidden, used_range}], dependencies,
  external_refs, extraction_gaps, vba_modules[名前のみ] を含む JSON 化可能 dict）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_machine.py`:

```python
from sheetlens.model import ir
from sheetlens.renderers.machine import build_manifest, sheet_dependencies


def _wb():
    return ir.Workbook(
        source_file="a.xlsx", sha256="00" * 32,
        sheets=[
            ir.Sheet(name="見積入力", used_range="A1:B2",
                     cells=[ir.Cell(ref="A1", formula="=VLOOKUP(B1,単価マスタ!A:C,3,0)"),
                            ir.Cell(ref="B2", formula="=[原価表.xlsx]原価!B2")]),
            ir.Sheet(name="単価マスタ", used_range="A1:C9", cells=[ir.Cell(ref="A1", value="品名")]),
        ],
        vba_modules=[ir.VbaModule(name="Module1.bas", code="")],
        extraction_gaps=["gap1"],
    )


def test_dependencies():
    assert sheet_dependencies(_wb()) == {"見積入力": ["単価マスタ"], "単価マスタ": []}


def test_manifest_shape():
    m = build_manifest(_wb())
    assert m["source_file"] == "a.xlsx"
    assert m["sheets"][0] == {"name": "見積入力", "hidden": False, "used_range": "A1:B2"}
    assert m["dependencies"]["見積入力"] == ["単価マスタ"]
    assert m["external_refs"] == ["原価表.xlsx"]
    assert m["extraction_gaps"] == ["gap1"]
    assert m["vba_modules"] == ["Module1.bas"]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_machine.py -v`
Expected: FAIL（モジュールなし）

- [ ] **Step 3: 実装**

`src/sheetlens/renderers/machine.py`:

```python
import re

from sheetlens.model import ir

_EXT_RE = re.compile(r"\[([^\]]+\.xls[xmb]?)\]")


def external_references(wb: ir.Workbook) -> list[str]:
    found: set[str] = set()
    for sheet in wb.sheets:
        for cell in sheet.cells:
            if cell.formula:
                found.update(_EXT_RE.findall(cell.formula))
    return sorted(found)


def sheet_dependencies(wb: ir.Workbook) -> dict[str, list[str]]:
    names = [s.name for s in wb.sheets]
    deps: dict[str, list[str]] = {}
    for sheet in wb.sheets:
        found: set[str] = set()
        for cell in sheet.cells:
            if not cell.formula:
                continue
            for name in names:
                if name != sheet.name and (f"'{name}'!" in cell.formula or f"{name}!" in cell.formula):
                    found.add(name)
        deps[sheet.name] = sorted(found)
    return deps


def build_manifest(wb: ir.Workbook) -> dict:
    return {
        "source_file": wb.source_file,
        "sha256": wb.sha256,
        "sheets": [
            {"name": s.name, "hidden": s.hidden, "used_range": s.used_range} for s in wb.sheets
        ],
        "dependencies": sheet_dependencies(wb),
        "external_refs": sorted(set(wb.external_refs) | set(external_references(wb))),
        "extraction_gaps": wb.extraction_gaps,
        "vba_modules": [m.name for m in wb.vba_modules],
    }
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_machine.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add src/sheetlens/renderers tests/test_machine.py
git commit -m "feat: renderers — manifest とシート間依存グラフ"
```

---

### Task 11: renderers — Markdown ビュー（シート / README / questions）

**Files:**
- Create: `src/sheetlens/renderers/markdown.py`
- Test: `tests/test_markdown.py`

**Interfaces:**
- Consumes: `ir.*`, `FormulaPattern`, `Region`, `Question`, `SheetAnnotations`
- Produces:
  - `render_sheet_md(sheet, patterns, regions, questions, buttons, ann=None, answered=frozenset()) -> str`
  - `render_readme(wb, deps, questions, answered) -> str`（extraction_gaps があれば冒頭に ⚠ 警告）
  - `render_questions_md(questions, answered) -> str`（回答済みは `[x]`）
- 仕様: 注釈は該当要素の直下に `> 💬 業務上の意味:` として織り込む（対象は `range` の完全一致）。
  そのシートの未回答質問は末尾に `> ❓ 未確認:` として列挙する。レイアウトマップは 40 行 × 15 列で
  打ち切り、打ち切った場合は「以降は raw.json を参照」と明記する。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_markdown.py`:

```python
from sheetlens.annotations.schema import AnnotationTarget, SheetAnnotations
from sheetlens.detectors.formula_patterns import FormulaPattern
from sheetlens.detectors.questions import Question
from sheetlens.detectors.regions import Region
from sheetlens.model import ir
from sheetlens.renderers.markdown import render_questions_md, render_readme, render_sheet_md


def _sheet():
    return ir.Sheet(
        name="見積入力",
        used_range="A1:E12",
        cells=[
            ir.Cell(ref="A1", value="見積書"),
            ir.Cell(ref="A3", value="顧客名"),
            ir.Cell(ref="E11", value=None, formula="=C11*D11"),
        ],
        merged=["A1:C1"],
        validations=[ir.ValidationRule(ranges=["C5"], type="list", choices=["通常", "特急"])],
        conditional_formats=[
            ir.ConditionalFormat(range="F11:F30", rule_type="cellIs", operator="lessThan", formula="0")
        ],
    )


def test_sheet_md_mentions_structure():
    md = render_sheet_md(
        _sheet(),
        [FormulaPattern(ranges=["E11:E30"], pattern="=C{row}*D{row}", example="=C11*D11",
                        exceptions=["E15: =C15*D15*1.1"])],
        [Region(range="A3:B8", kind="block")],
        [],
        [ir.ButtonLink(sheet="見積入力", macro="Module1.Register")],
    )
    assert "# シート: 見積入力" in md
    assert "[A1:C1 結合]" in md
    assert "E11:E30" in md and "=C{row}*D{row}" in md
    assert "E15: =C15*D15*1.1" in md  # 例外の強調
    assert "通常" in md and "特急" in md
    assert "lessThan 0" in md
    assert "Module1.Register" in md


def test_annotations_and_unanswered_woven_in():
    ann = SheetAnnotations(
        sheet="見積入力", role="営業のメイン入力画面",
        targets=[AnnotationTarget(range="A3:B8", kind="input_source", value="manual", by="営業担当")],
    )
    qs = [Question(id="q-001", sheet="見積入力", target="A3:B8", category="input_source", text="誰が入力？")]
    md = render_sheet_md(_sheet(), [], [Region(range="A3:B8", kind="block")], qs, [], ann, frozenset())
    assert "💬 業務上の意味" in md and "営業担当" in md and "営業のメイン入力画面" in md
    assert "❓ 未確認" in md and "q-001" in md
    md_answered = render_sheet_md(_sheet(), [], [Region(range="A3:B8", kind="block")], qs, [], ann, {"q-001"})
    assert "q-001" not in md_answered


def test_readme_warns_on_gaps():
    wb = ir.Workbook(source_file="a.xlsx", sha256="00" * 32,
                     sheets=[ir.Sheet(name="s")], extraction_gaps=["x の抽出に失敗"])
    md = render_readme(wb, {"s": []}, [], frozenset())
    assert "⚠" in md and "1 件" in md


def test_questions_md_checkboxes():
    qs = [Question(id="q-001", sheet="s", target="A1", category="sheet_role", text="役割は？")]
    assert "- [ ] **q-001**" in render_questions_md(qs, frozenset())
    assert "- [x] **q-001**" in render_questions_md(qs, {"q-001"})
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_markdown.py -v`
Expected: FAIL（モジュールなし）

- [ ] **Step 3: 実装**

`src/sheetlens/renderers/markdown.py`:

```python
from collections.abc import Iterable

from openpyxl.utils import coordinate_to_tuple, get_column_letter, range_boundaries

from sheetlens.annotations.schema import AnnotationTarget, SheetAnnotations
from sheetlens.detectors.formula_patterns import FormulaPattern
from sheetlens.detectors.questions import Question
from sheetlens.detectors.regions import Region
from sheetlens.model import ir

MAX_GRID_ROWS = 40
MAX_GRID_COLS = 15


def _fmt_target(t: AnnotationTarget) -> str:
    if t.kind == "input_source":
        parts = [f"入力元: {t.value}"] if t.value else []
        if t.by:
            parts.append(f"入力者: {t.by}")
        if t.when:
            parts.append(f"タイミング: {t.when}")
        return " / ".join(parts) or (t.note or "")
    if t.kind == "dropdown_semantics" and t.values:
        return "選択肢の意味: " + "、".join(f"「{k}」={v}" for k, v in t.values.items())
    return t.note or t.value or ""


def _ann_lines(ann: SheetAnnotations | None, rng: str) -> list[str]:
    if not ann:
        return []
    lines = [f"> 💬 業務上の意味: {_fmt_target(t)}" for t in ann.targets if t.range == rng]
    return lines + [""] if lines else []


def _grid(sheet: ir.Sheet) -> list[str]:
    if not sheet.cells or not sheet.used_range:
        return ["（空シート）", ""]
    cellmap = {c.ref: c for c in sheet.cells}
    anchors: dict[str, str] = {}
    covered: set[tuple[int, int]] = set()
    for m in sheet.merged:
        min_c, min_r, max_c, max_r = range_boundaries(m)
        anchors[f"{get_column_letter(min_c)}{min_r}"] = m
        covered.update(
            (r, c)
            for r in range(min_r, max_r + 1)
            for c in range(min_c, max_c + 1)
            if (r, c) != (min_r, min_c)
        )
    min_c, min_r, max_c, max_r = range_boundaries(sheet.used_range)
    trunc = max_r - min_r + 1 > MAX_GRID_ROWS or max_c - min_c + 1 > MAX_GRID_COLS
    max_r = min(max_r, min_r + MAX_GRID_ROWS - 1)
    max_c = min(max_c, min_c + MAX_GRID_COLS - 1)
    cols = [get_column_letter(c) for c in range(min_c, max_c + 1)]
    lines = ["| 行 | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for r in range(min_r, max_r + 1):
        row: list[str] = []
        for c in range(min_c, max_c + 1):
            ref = f"{get_column_letter(c)}{r}"
            if (r, c) in covered:
                row.append("←")
                continue
            cell = cellmap.get(ref)
            text = "" if cell is None else str(cell.value if cell.value is not None else cell.formula or "")
            if ref in anchors:
                text = f"[{anchors[ref]} 結合] {text}".strip()
            row.append(text.replace("|", "\\|"))
        lines.append(f"| {r} | " + " | ".join(row) + " |")
    if trunc:
        lines.append("")
        lines.append(f"（{MAX_GRID_ROWS} 行 × {MAX_GRID_COLS} 列で打ち切り。以降は raw.json を参照）")
    return lines + [""]


def render_sheet_md(
    sheet: ir.Sheet,
    patterns: list[FormulaPattern],
    regions: list[Region],
    questions: list[Question],
    buttons: list[ir.ButtonLink],
    ann: SheetAnnotations | None = None,
    answered: Iterable[str] = frozenset(),
) -> str:
    answered = set(answered)
    lines = [f"# シート: {sheet.name}", ""]
    if ann and ann.role:
        stage = f"（工程: {ann.workflow_stage}）" if ann.workflow_stage else ""
        lines += [f"> 💬 業務上の意味: {ann.role}{stage}", ""]
    flags = []
    if sheet.hidden:
        flags.append("非表示シート")
    if sheet.protected:
        flags.append("保護あり")
    if sheet.hidden_cols:
        flags.append(f"非表示列: {', '.join(sheet.hidden_cols)}")
    lines += [
        "## 概要",
        f"- 使用範囲: {sheet.used_range or 'なし'} / 結合セル: {len(sheet.merged)} 箇所 / "
        f"数式セル: {sum(1 for c in sheet.cells if c.formula)} / 入力規則: {len(sheet.validations)}",
    ]
    if flags:
        lines.append(f"- 属性: {' / '.join(flags)}")
    lines += ["", "## レイアウトマップ", ""]
    lines += _grid(sheet)
    if regions:
        lines += ["## 領域", ""]
        for i, region in enumerate(regions, 1):
            kind = "テーブル" if region.kind == "table" else "ブロック"
            lines.append(f"### 領域{i}: {region.range} — {kind}")
            lines += _ann_lines(ann, region.range)
        lines.append("")
    if patterns:
        lines += ["## 数式（正規化済み）", ""]
        for p in patterns:
            lines.append(f"- {', '.join(p.ranges)} = `{p.pattern}`（例: `{p.example}`）")
            for ex in p.exceptions:
                lines.append(f"  - **⚠ 例外: {ex}**（パターンから逸脱。特例または誤りの可能性）")
        lines.append("")
    if sheet.validations:
        lines += ["## 入力規則（プルダウン等）", ""]
        for v in sheet.validations:
            choices = f" 選択肢: {', '.join(v.choices)}" if v.choices else ""
            lines.append(f"- {', '.join(v.ranges)}: {v.type}（{v.formula1 or ''}）{choices}")
            lines += _ann_lines(ann, v.ranges[0])
        lines.append("")
    if sheet.conditional_formats:
        lines += ["## 条件付き書式", ""]
        for cf in sheet.conditional_formats:
            cond = " ".join(x for x in (cf.operator, cf.formula) if x) or cf.rule_type
            lines.append(f"- {cf.range}: {cf.rule_type} — 条件: {cond}")
            lines += _ann_lines(ann, cf.range)
        lines.append("")
    if buttons:
        lines += ["## VBA との接続", ""]
        for b in buttons:
            label = f"「{b.label}」" if b.label else ""
            lines.append(f"- ボタン{label} → {b.macro}")
        lines.append("")
    unanswered = [q for q in questions if q.sheet == sheet.name and q.id not in answered]
    if unanswered:
        lines += ["## 未確認事項", ""]
        for q in unanswered:
            lines.append(f"> ❓ 未確認 ({q.id}): [{q.target}] {q.text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_readme(
    wb: ir.Workbook,
    deps: dict[str, list[str]],
    questions: list[Question],
    answered: Iterable[str],
) -> str:
    answered = set(answered)
    lines = [f"# {wb.source_file} — SheetLens 抽出結果", ""]
    if wb.extraction_gaps:
        lines += [f"**⚠ この抽出には {len(wb.extraction_gaps)} 件の欠落があります:**", ""]
        lines += [f"- {g}" for g in wb.extraction_gaps]
        lines.append("")
    lines += [
        "## 読み方",
        "",
        "- `structure/sheet-*.md`: シートごとの構造ビュー（compile 後は業務注釈も織り込み済み）",
        "- `structure/raw.json`: 省略なしの全抽出データ（機械可読の正）",
        "- `structure/vba/*.bas`: VBA ソース",
        "- `annotations/*.yaml`: 業務上の意味（人間の回答。手で編集してよい唯一の場所）",
        "- `questions.md`: 業務担当者に確認すべき質問リスト",
        "",
        "## シート一覧",
        "",
    ]
    for s in wb.sheets:
        mark = "（非表示）" if s.hidden else ""
        lines.append(f"- {s.name}{mark}: 使用範囲 {s.used_range or 'なし'}")
    edges = [(a, bs) for a, bs in deps.items() if bs]
    if edges:
        lines += ["", "## シート間依存（参照する側 → される側）", ""]
        lines += [f"- {a} → {', '.join(bs)}" for a, bs in edges]
    unanswered = sum(1 for q in questions if q.id not in answered)
    lines += ["", f"## 未確認事項: {unanswered} 件（`questions.md` 参照）"]
    return "\n".join(lines).rstrip() + "\n"


def render_questions_md(questions: list[Question], answered: Iterable[str]) -> str:
    answered = set(answered)
    lines = [
        "# 業務担当者への質問リスト",
        "",
        "回答は `annotations/<シート名>.yaml` に記録し、`questions_answered` に ID を追加すること。",
        "",
    ]
    for q in questions:
        mark = "x" if q.id in answered else " "
        lines.append(f"- [{mark}] **{q.id}** [{q.sheet} / {q.target}] ({q.category}) {q.text}")
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_markdown.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add src/sheetlens/renderers/markdown.py tests/test_markdown.py
git commit -m "feat: renderers — シート/README/questions の Markdown ビュー"
```

---

### Task 12: pipeline + extract コマンド（E2E 統合）

**Files:**
- Create: `src/sheetlens/pipeline.py`
- Modify: `src/sheetlens/cli.py`（extract を実装に差し替え）
- Test: `tests/test_extract_e2e.py`

**Interfaces:**
- Produces: `Analysis(patterns: dict[str, list[FormulaPattern]], regions: dict[str, list[Region]], questions: list[Question])` /
  `analyze(wb: ir.Workbook) -> Analysis` /
  `extract_workbook(src: Path, out: Path | None = None) -> Path`（プロジェクトディレクトリを返す）
- 仕様: 出力先は `-o` 未指定なら `<src の stem>.sheetlens`（src と同じディレクトリ）。
  extract は注釈**なし**のビューを書く（注釈の織り込みは compile の仕事、設計書どおり）。
  `annotations/` は存在しなければ空で作成し、既存の中身には一切触れない。
  シート名のファイル名化は `/` を `_` に置換する。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_extract_e2e.py`:

```python
import json

from openpyxl.worksheet.datavalidation import DataValidation
from typer.testing import CliRunner

from sheetlens.cli import app

runner = CliRunner()


def _build(wb):
    ws = wb.active
    ws.title = "見積入力"
    ws["A1"] = "見積書"
    ws.merge_cells("A1:C1")
    ws["A3"] = "顧客名"
    for r in range(11, 14):
        ws[f"C{r}"] = 2
        ws[f"D{r}"] = f"=VLOOKUP(A{r},単価マスタ!A:C,3,0)"
        ws[f"E{r}"] = f"=C{r}*D{r}"
    dv = DataValidation(type="list", formula1='"通常,特急"')
    dv.add("C5")
    ws.add_data_validation(dv)
    master = wb.create_sheet("単価マスタ")
    master["A1"] = "品名"


def test_extract_generates_project(make_xlsx):
    src = make_xlsx(_build, name="見積管理.xlsx")
    result = runner.invoke(app, ["extract", str(src)])
    assert result.exit_code == 0, result.output
    proj = src.parent / "見積管理.sheetlens"
    for rel in ("manifest.json", "questions.md", "README.md",
                "structure/raw.json", "structure/sheet-見積入力.md", "annotations"):
        assert (proj / rel).exists(), rel
    manifest = json.loads((proj / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dependencies"]["見積入力"] == ["単価マスタ"]
    md = (proj / "structure/sheet-見積入力.md").read_text(encoding="utf-8")
    assert "[A1:C1 結合]" in md
    assert "=C{row}*D{row}" in md
    assert "通常" in md
    questions = (proj / "questions.md").read_text(encoding="utf-8")
    assert "dropdown_semantics" in questions and "sheet_role" in questions


def test_extract_preserves_annotations(make_xlsx):
    src = make_xlsx(_build, name="a.xlsx")
    proj = src.parent / "a.sheetlens"
    (proj / "annotations").mkdir(parents=True)
    keep = proj / "annotations" / "見積入力.yaml"
    keep.write_text("sheet: 見積入力\n", encoding="utf-8")
    result = runner.invoke(app, ["extract", str(src)])
    assert result.exit_code == 0, result.output
    assert keep.read_text(encoding="utf-8") == "sheet: 見積入力\n"


def test_extract_rejects_broken_file(tmp_path):
    bad = tmp_path / "broken.xlsx"
    bad.write_bytes(b"not a zip")
    result = runner.invoke(app, ["extract", str(bad)])
    assert result.exit_code == 1
    assert "読めません" in result.output
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_extract_e2e.py -v`
Expected: FAIL（extract: 未実装で exit 1）

- [ ] **Step 3: 実装**

`src/sheetlens/pipeline.py`:

```python
import json
from pathlib import Path

from pydantic import BaseModel

from sheetlens.annotations.schema import SheetAnnotations, load_annotations
from sheetlens.detectors.formula_patterns import FormulaPattern, aggregate_formulas
from sheetlens.detectors.questions import Question, generate_questions
from sheetlens.detectors.regions import Region, detect_regions
from sheetlens.model import ir
from sheetlens.reader.workbook import read_workbook
from sheetlens.renderers.machine import build_manifest, sheet_dependencies
from sheetlens.renderers.markdown import render_questions_md, render_readme, render_sheet_md


class Analysis(BaseModel):
    patterns: dict[str, list[FormulaPattern]]
    regions: dict[str, list[Region]]
    questions: list[Question]


def analyze(wb: ir.Workbook) -> Analysis:
    patterns = {s.name: aggregate_formulas(s) for s in wb.sheets}
    regions = {s.name: detect_regions(s) for s in wb.sheets}
    return Analysis(
        patterns=patterns, regions=regions, questions=generate_questions(wb, regions, patterns)
    )


def _safe(name: str) -> str:
    return name.replace("/", "_")


def _write_views(
    proj: Path,
    wb: ir.Workbook,
    analysis: Analysis,
    anns: list[SheetAnnotations],
    answered: set[str],
) -> None:
    structure = proj / "structure"
    ann_map = {a.sheet: a for a in anns}
    for sheet in wb.sheets:
        md = render_sheet_md(
            sheet,
            analysis.patterns[sheet.name],
            analysis.regions[sheet.name],
            analysis.questions,
            [b for b in wb.buttons if b.sheet == sheet.name],
            ann_map.get(sheet.name),
            answered,
        )
        (structure / f"sheet-{_safe(sheet.name)}.md").write_text(md, encoding="utf-8")
    (proj / "README.md").write_text(
        render_readme(wb, sheet_dependencies(wb), analysis.questions, answered), encoding="utf-8"
    )
    (proj / "questions.md").write_text(
        render_questions_md(analysis.questions, answered), encoding="utf-8"
    )


def extract_workbook(src: Path, out: Path | None = None) -> Path:
    wb = read_workbook(src)
    proj = out or src.with_name(src.stem + ".sheetlens")
    (proj / "structure").mkdir(parents=True, exist_ok=True)
    (proj / "annotations").mkdir(exist_ok=True)  # 既存の中身には触れない
    (proj / "structure" / "raw.json").write_text(wb.model_dump_json(indent=2), encoding="utf-8")
    (proj / "manifest.json").write_text(
        json.dumps(build_manifest(wb), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if wb.vba_modules:
        vba_dir = proj / "structure" / "vba"
        vba_dir.mkdir(exist_ok=True)
        for m in wb.vba_modules:
            (vba_dir / f"{_safe(m.name)}.bas").write_text(m.code, encoding="utf-8")
    # extract は注釈なしのビューを書く（織り込みは compile の仕事）
    _write_views(proj, wb, analyze(wb), [], set())
    return proj
```

`src/sheetlens/cli.py` の `extract` を差し替え:

```python
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException


@app.command()
def extract(file: Path, out: Path | None = typer.Option(None, "-o", "--out")) -> None:
    """xlsx/xlsm から構造層と questions.md を生成する。"""
    from sheetlens.pipeline import extract_workbook

    try:
        proj = extract_workbook(file, out)
    except (InvalidFileException, BadZipFile, KeyError) as e:
        typer.echo(f"エラー: {file} を読めません（破損またはパスワード保護の可能性）: {e}")
        raise typer.Exit(1) from e
    typer.echo(f"生成しました: {proj}")
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest -v`
Expected: 全テスト PASS

- [ ] **Step 5: コミット**

```bash
git add src/sheetlens/pipeline.py src/sheetlens/cli.py tests/test_extract_e2e.py
git commit -m "feat: extract コマンド — E2E パイプライン統合"
```

---

### Task 13: compile コマンド — 注釈の織り込み

**Files:**
- Modify: `src/sheetlens/pipeline.py`（`compile_project` を追加）
- Modify: `src/sheetlens/cli.py`（compile を実装に差し替え）
- Test: `tests/test_compile_e2e.py`

**Interfaces:**
- Produces: `compile_project(proj: Path) -> list[str]`（孤立注釈の警告リストを返す）
- 仕様: `structure/raw.json` から `ir.Workbook` を復元し（Excel 原本不要）、annotations/ を読んで
  ビューを再生成する。孤立注釈は警告として stdout に出すが exit 0（自動削除しない、設計書どおり）。
  注釈スキーマ違反は exit 1。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_compile_e2e.py`:

```python
from typer.testing import CliRunner

from sheetlens.cli import app

runner = CliRunner()

ANNOTATION = """\
sheet: 見積入力
role: "営業担当のメイン入力画面"
targets:
  - range: A3:B3
    kind: input_source
    value: manual
    by: "営業担当"
  - range: Z100:Z200
    kind: free_note
    note: "消えた範囲への注釈"
questions_answered: [q-001]
"""


def _extract(make_xlsx):
    def _build(wb):
        ws = wb.active
        ws.title = "見積入力"
        ws["A3"] = "顧客名"
        ws["B3"] = "株式会社サンプル"

    src = make_xlsx(_build, name="a.xlsx")
    assert runner.invoke(app, ["extract", str(src)]).exit_code == 0
    return src.parent / "a.sheetlens"


def test_compile_weaves_annotations(make_xlsx):
    proj = _extract(make_xlsx)
    (proj / "annotations" / "見積入力.yaml").write_text(ANNOTATION, encoding="utf-8")
    result = runner.invoke(app, ["compile", str(proj)])
    assert result.exit_code == 0, result.output
    md = (proj / "structure" / "sheet-見積入力.md").read_text(encoding="utf-8")
    assert "💬 業務上の意味: 営業担当のメイン入力画面" in md
    assert "q-001" not in md  # 回答済み質問は未確認に出ない
    assert "Z100:Z200" in result.output  # 孤立注釈の警告
    questions = (proj / "questions.md").read_text(encoding="utf-8")
    assert "- [x] **q-001**" in questions


def test_compile_rejects_broken_annotation(make_xlsx):
    proj = _extract(make_xlsx)
    (proj / "annotations" / "bad.yaml").write_text("sheet: s\ntargets:\n  - kind: nope\n", encoding="utf-8")
    result = runner.invoke(app, ["compile", str(proj)])
    assert result.exit_code == 1
    assert "bad.yaml" in result.output
```

**注記:** 領域検出は「A3:B3」の 1 行帯を `A3:B3` の block として検出するため、
`range: A3:B3` の注釈が領域に一致して織り込まれる。

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_compile_e2e.py -v`
Expected: FAIL（compile: 未実装で exit 1）

- [ ] **Step 3: 実装**

`src/sheetlens/pipeline.py` に追加:

```python
from sheetlens.annotations.schema import find_orphans


def compile_project(proj: Path) -> list[str]:
    wb = ir.Workbook.model_validate_json(
        (proj / "structure" / "raw.json").read_text(encoding="utf-8")
    )
    anns = load_annotations(proj / "annotations")
    answered = {qid for a in anns for qid in a.questions_answered}
    _write_views(proj, wb, analyze(wb), anns, answered)
    return find_orphans(wb, anns)
```

`src/sheetlens/cli.py` の `compile_cmd` を差し替え:

```python
@app.command(name="compile")
def compile_cmd(project: Path) -> None:
    """構造層 + 注釈を統合した Markdown を再生成する。"""
    from sheetlens.annotations.schema import AnnotationError
    from sheetlens.pipeline import compile_project

    try:
        orphans = compile_project(project)
    except AnnotationError as e:
        typer.echo(f"注釈エラー: {e}")
        raise typer.Exit(1) from e
    for o in orphans:
        typer.echo(f"警告（孤立注釈）: {o}")
    typer.echo(f"再生成しました: {project}")
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest -v`
Expected: 全テスト PASS

- [ ] **Step 5: コミット**

```bash
git add src/sheetlens/pipeline.py src/sheetlens/cli.py tests/test_compile_e2e.py
git commit -m "feat: compile コマンド — 注釈の織り込みと孤立注釈警告"
```

---

### Task 14: check コマンド

**Files:**
- Modify: `src/sheetlens/cli.py`（check を実装に差し替え）
- Test: `tests/test_check_e2e.py`

**Interfaces:**
- 仕様: raw.json + annotations/ を読み、①スキーマ違反 → exit 1、②孤立注釈と未回答質問数を報告
  （孤立があっても exit 0。破壊的動作はしない）。出力例:
  `孤立注釈: 見積入力!Z100:Z200: ...` / `未回答質問: 3 / 5`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_check_e2e.py`:

```python
from typer.testing import CliRunner

from sheetlens.cli import app

runner = CliRunner()


def _extract(make_xlsx, name="a.xlsx"):
    def _build(wb):
        ws = wb.active
        ws.title = "入力"
        ws["A1"] = "データ"

    src = make_xlsx(_build, name=name)
    assert runner.invoke(app, ["extract", str(src)]).exit_code == 0
    return src.parent / (src.stem + ".sheetlens")


def test_check_reports_counts(make_xlsx):
    proj = _extract(make_xlsx)
    (proj / "annotations" / "入力.yaml").write_text(
        "sheet: 入力\nquestions_answered: [q-001]\n", encoding="utf-8"
    )
    result = runner.invoke(app, ["check", str(proj)])
    assert result.exit_code == 0, result.output
    assert "未回答質問:" in result.output


def test_check_fails_on_schema_error(make_xlsx):
    proj = _extract(make_xlsx)
    (proj / "annotations" / "bad.yaml").write_text("sheet: s\ntargets:\n  - kind: nope\n", encoding="utf-8")
    result = runner.invoke(app, ["check", str(proj)])
    assert result.exit_code == 1
    assert "bad.yaml" in result.output
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_check_e2e.py -v`
Expected: FAIL（check: 未実装で exit 1 だがメッセージ不一致）

- [ ] **Step 3: 実装**

`src/sheetlens/cli.py` の `check` を差し替え:

```python
@app.command()
def check(project: Path) -> None:
    """孤立注釈・未回答質問・スキーマ違反を報告する。"""
    from sheetlens.annotations.schema import AnnotationError, find_orphans, load_annotations
    from sheetlens.model import ir
    from sheetlens.pipeline import analyze

    wb = ir.Workbook.model_validate_json(
        (project / "structure" / "raw.json").read_text(encoding="utf-8")
    )
    try:
        anns = load_annotations(project / "annotations")
    except AnnotationError as e:
        typer.echo(f"注釈エラー: {e}")
        raise typer.Exit(1) from e
    for o in find_orphans(wb, anns):
        typer.echo(f"孤立注釈: {o}")
    questions = analyze(wb).questions
    answered = {qid for a in anns for qid in a.questions_answered}
    unanswered = sum(1 for q in questions if q.id not in answered)
    typer.echo(f"未回答質問: {unanswered} / {len(questions)}")
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest -v && uv run ruff check .`
Expected: 全テスト PASS / ruff エラーなし

- [ ] **Step 5: コミット**

```bash
git add src/sheetlens/cli.py tests/test_check_e2e.py
git commit -m "feat: check コマンド — 孤立注釈と未回答質問の報告"
```

---

### Task 15: QA 評価ハーネス（eval/）

**Files:**
- Create: `eval/make_dummy.py`
- Create: `eval/questions.yaml`
- Create: `eval/README.md`
- Test: `tests/test_eval_dummy.py`

**Interfaces:**
- Produces: `eval/make_dummy.py` — 実行すると `eval/見積管理.xlsx`（記憶ベースのダミー業務 Excel）を生成する
  スクリプト。`python eval/make_dummy.py` で実行（uv 環境内）。
- 仕様: これが設計書の成功基準「AI の QA 正答率」の評価基盤。ダミーの内容はユーザーへの
  ヒアリングで今後拡充する（このタスクでは見積管理の最小構成を作る）。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_eval_dummy.py`:

```python
import subprocess
import sys
from pathlib import Path


def test_make_dummy_then_extract(tmp_path):
    out = tmp_path / "見積管理.xlsx"
    subprocess.run(
        [sys.executable, "eval/make_dummy.py", str(out)],
        check=True, cwd=Path(__file__).parent.parent,
    )
    assert out.exists()
    from sheetlens.pipeline import extract_workbook

    proj = extract_workbook(out)
    md = (proj / "structure" / "sheet-見積入力.md").read_text(encoding="utf-8")
    assert "VLOOKUP" in md  # 単価の参照数式がパターンとして出る
    assert "通常" in md and "特急" in md  # プルダウン選択肢の展開
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_eval_dummy.py -v`
Expected: FAIL（eval/make_dummy.py がない）

- [ ] **Step 3: 実装**

`eval/make_dummy.py`:

```python
"""記憶ベースのダミー業務 Excel（見積管理）を生成する。

使い方: uv run python eval/make_dummy.py [出力パス]
中身はユーザーへのヒアリングで現実の業務パターンに近づけていく。
"""

import sys
from pathlib import Path

import openpyxl
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation


def build(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "見積入力"
    ws.merge_cells("A1:H1")
    ws["A1"] = "見積書"
    ws["A1"].font = Font(size=16, bold=True)
    ws["A3"] = "顧客名"
    ws["A4"] = "見積日"
    ws["A5"] = "区分"
    dv = DataValidation(type="list", formula1="=区分マスタ!$A$2:$A$3")
    dv.add("B5")
    ws.add_data_validation(dv)
    ws["A10"] = "No"
    ws["B10"] = "品名"
    ws["C10"] = "数量"
    ws["D10"] = "単価"
    ws["E10"] = "金額"
    ws["F10"] = "粗利"
    for r in range(11, 31):
        ws[f"A{r}"] = r - 10
        ws[f"D{r}"] = f"=IFERROR(VLOOKUP(B{r},単価マスタ!$A$2:$C$9,3,FALSE),0)"
        ws[f"E{r}"] = f"=C{r}*D{r}"
        ws[f"F{r}"] = f"=E{r}-C{r}*VLOOKUP(B{r},単価マスタ!$A$2:$C$9,2,FALSE)"
    ws["E32"] = "=SUM(E11:E30)"
    red = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    ws.conditional_formatting.add(
        "F11:F30", CellIsRule(operator="lessThan", formula=["0"], fill=red)
    )
    master = wb.create_sheet("単価マスタ")
    master.append(["品名", "原価", "単価"])
    for row in (["部品A", 700, 1000], ["部品B", 3500, 5000], ["組立費", 6000, 8000]):
        master.append(row)
    kubun = wb.create_sheet("区分マスタ")
    kubun.append(["区分"])
    kubun.append(["通常"])
    kubun.append(["特急"])
    kubun.sheet_state = "hidden"
    wb.save(path)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "見積管理.xlsx"
    build(out)
    print(f"生成しました: {out}")
```

`eval/questions.yaml`:

```yaml
# QA 評価用の質問セット。expected は人間が採点するときの模範解答。
# 評価対象の AI には expected を見せないこと。
target: 見積管理.xlsx
questions:
  - id: e-001
    q: "E15 セルの値はどうやって決まりますか？"
    expected: "数式 =C15*D15（数量×単価）で自動計算される"
  - id: e-002
    q: "D 列（単価）は手入力ですか？"
    expected: "いいえ。単価マスタから VLOOKUP で自動参照される（IFERROR で未登録品は 0）"
  - id: e-003
    q: "B5 にはどんな値を入れられますか？"
    expected: "プルダウンで「通常」「特急」の 2 択（区分マスタ参照）"
  - id: e-004
    q: "F 列が赤くなるのはどんなときですか？"
    expected: "粗利（F列）が 0 未満（マイナス）のとき"
  - id: e-005
    q: "A1 の「見積書」はどの範囲に表示されていますか？"
    expected: "A1:H1 の結合セル"
  - id: e-006
    q: "見積入力シートはどのシートに依存していますか？"
    expected: "単価マスタ（VLOOKUP）と区分マスタ（プルダウンのリスト参照）"
  - id: e-007
    q: "このブックに非表示のシートはありますか？"
    expected: "区分マスタが非表示"
  - id: e-008
    q: "E32 は何を表していますか？"
    expected: "明細金額（E11:E30）の合計"
```

`eval/README.md`:

```markdown
# QA 評価ハーネス

設計書の成功基準「中間表現だけを読んだ AI の QA 正答率」を測る手順。

## 準備

1. `uv run python eval/make_dummy.py` で `eval/見積管理.xlsx` を生成
2. `uv run sheetlens extract eval/見積管理.xlsx` で `eval/見積管理.sheetlens/` を生成

## 評価手順（A/B 比較）

1. **条件 A（ベースライン）**: 新しい AI セッションに `見積管理.xlsx` だけを渡し、
   `questions.yaml` の各質問をぶつける（expected は見せない）
2. **条件 B**: 別の新しいセッションに `見積管理.sheetlens/` だけを渡し、同じ質問をぶつける
3. 各回答を expected と突き合わせて正誤を記録し、正答率を比較する

## 判定

条件 B の正答率が条件 A を明確に上回れば v1 の成功。同等以下なら中間表現の
フォーマットを見直す（結果は docs/ に記録する）。

## 拡充

ダミー Excel はユーザーへのヒアリングで現実の業務パターン（VBA ボタン、
複数シート連携、帳票レイアウト等）に近づけていく。質問セットも同時に増やす。
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_eval_dummy.py -v`
Expected: PASS

- [ ] **Step 5: 全体確認とコミット**

Run: `uv run pytest -v && uv run ruff check .`
Expected: 全テスト PASS / ruff エラーなし

```bash
git add eval tests/test_eval_dummy.py
git commit -m "feat: QA 評価ハーネス — ダミー業務 Excel と質問セット"
```

---

## 実装後の残作業（このプランのスコープ外・忘れないための記録）

- ユーザーへのヒアリングでダミー Excel を現実の業務パターンに拡充（eval/README.md の手順）
- QA 評価（A/B 比較)の実施と結果の記録
- 業務 PC での実地検証: 実 .xlsm での VBA 抽出・extraction_gaps の確認（Task 5 のモック部分の実機補完）
- CLAUDE.md への知見の追記
