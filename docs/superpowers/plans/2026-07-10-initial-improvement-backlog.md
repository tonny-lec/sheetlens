# SheetLens Initial Improvement Backlog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2026-07-10 のリポジトリ全体監査で確認した改善点を、根拠、依存、受け入れ条件、変更予定範囲を持つ 17 件の管理課題として登録する。

**Architecture:** Project Management Foundation が提供する Markdown 課題形式へ、監査結果をマイルストーン単位で移行する。各追加後に `render` と `check` を実行し、課題ファイルを正本、backlog を生成物として同期させる。

**Tech Stack:** Markdown、YAML front matter、`scripts/check_project_state.py`

## Global Constraints

- この計画は `2026-07-10-project-management-foundation.md` の完了後に実行する。
- 実行開始前に書き込み可能な Git 環境で専用 branch/worktree を作る。`main` に直接コミットしない。
- 課題の本文は調査済み事実と明示した対象外だけを記載し、新しい設計判断を混ぜない。
- すべての課題に最低 1 件の `file:line` 根拠と、実行可能な受け入れ条件を記載する。
- `owner` は全件 null で開始する。依存を満たす独立課題だけを `ready` にする。
- 初期登録は bootstrap 期間として、親ワーカーが明示した課題ファイルの新規作成をサブエージェントへ委譲できる。
- 初期登録と検証の完了後は、課題状態、担当、依存、backlog の更新を親ワーカーだけが行う。
- 各タスクの最後に backlog を再生成し、管理状態を検証する。

---

## 共通課題記述規約

各課題は Foundation で確定した front matter の順序を使い、各 Step に列挙した metadata、
touches、根本原因、根拠、受け入れ条件、対象外を課題本文へ記載する。各 Step で列挙した
受け入れ条件は、1 条件につき 1 行の未チェック `- [ ] ...` item として直列化する。plain bullet
や fenced example に置き換えない。本文見出しは
`背景と根本原因`、`根拠`、`受け入れ条件`、`対象外`、`実装計画`、`完了証拠` の順とする。

全課題の `実装計画` は次の文で開始する。

```text
着手時に `docs/superpowers/plans/` へ実装計画を作成し、ここからリンクする。
```

全課題の未完了時の `完了証拠` は次の文とする。

```text
完了時に検証コマンド、結果、レビュー結果を記録する。
```

### Task 1: M1 意味層の整合性を登録する

**Files:**
- Create: `docs/project/items/SL-001-stable-question-ids.md`
- Create: `docs/project/items/SL-002-annotation-schema.md`
- Create: `docs/project/items/SL-003-typed-element-ids.md`
- Create: `docs/project/items/SL-004-compiled-semantics.md`
- Modify: `docs/project/backlog.md`

**Interfaces:**
- Consumes: Foundation の課題 parser、validator、renderer
- Produces: M1 の 4 課題

- [ ] **Step 1: SL-001 を次の内容で作成する**

- Metadata: `status=ready`、`priority=P1`、`type=defect`、`milestone=M1`、`depends_on=[]`
- Touches: `src/sheetlens/detectors/questions.py`、`src/sheetlens/annotations/schema.py`、`src/sheetlens/pipeline.py`、`tests/test_questions.py`、`tests/test_compile_e2e.py`
- 背景と根本原因: 質問 ID が意味ではなく走査順の連番であり、前方へ質問が追加されると既存回答が別質問へ対応する。
- 根拠: `src/sheetlens/detectors/questions.py:39-40`、`src/sheetlens/pipeline.py:131`。親監査で同じ Input シートの役割質問が `q-001` から `q-003` へ変化することを再現済み。
- 受け入れ条件:
  - `sheet/category/target` の正規化値から決定的な ID または fingerprint を生成する。
  - 前方へシート、非表示属性、入力規則を追加しても既存質問 ID が変化しない。
  - 旧連番 ID の移行または stale 警告を提供する。
  - 削除・内容変更された質問 ID を `check` が報告する。
- 対象外: 質問文の全面的な文言変更と新しい質問カテゴリの追加。

- [ ] **Step 2: SL-002 を次の内容で作成する**

- Metadata: `status=proposed`、`priority=P1`、`type=defect`、`milestone=M1`、`depends_on=[SL-001]`
- Touches: `src/sheetlens/annotations/schema.py`、`src/sheetlens/pipeline.py`、`src/sheetlens/renderers/markdown.py`、`tests/test_annotations.py`、`tests/test_compile_e2e.py`
- 背景と根本原因: 注釈は kind ごとの必須値を持たず、同一シートの複数 YAML は表示時に最後の 1 件だけ残る一方、回答 ID は全ファイルから合算される。
- 根拠: `src/sheetlens/annotations/schema.py:19-38`、`src/sheetlens/pipeline.py:75`、`src/sheetlens/pipeline.py:131`。親監査で role は後者だけ、answered は両ファイル分になることを再現済み。
- 受け入れ条件:
  - kind 別 discriminated union で必須フィールドと許容フィールドを検証する。
  - 同一シート注釈を損失なくマージするか、ファイル名付きエラーとして拒否する。
  - 未知、廃止、対象不一致の質問 ID を検出する。
  - 空の input_source や内容のない回答を回答済みにできない。
- 対象外: 注釈入力用 GUI と外部データベース。

- [ ] **Step 3: SL-003 を次の内容で作成する**

- Metadata: `status=proposed`、`priority=P1`、`type=refactor`、`milestone=M1`、`depends_on=[SL-001, SL-002]`
- Touches: `src/sheetlens/model/ir.py`、`src/sheetlens/detectors/regions.py`、`src/sheetlens/detectors/formula_patterns.py`、`src/sheetlens/detectors/questions.py`、`src/sheetlens/annotations/schema.py`、`src/sheetlens/pipeline.py`、`src/sheetlens/renderers/markdown.py`
- 背景と根本原因: range 文字列だけでは数式パターン、例外式、VBA イベントへ意味注釈を安定して接続できず、Excel 更新後の同一性も表現できない。
- 根拠: `src/sheetlens/pipeline.py:46-63` は range、入力規則、条件付き書式、macro だけを接続キーとし、`src/sheetlens/renderers/markdown.py:125-131` は数式注釈を描画しない。`src/sheetlens/detectors/questions.py:70-73` の VBA 質問は架空シート `(VBA)` に属する。
- 受け入れ条件:
  - region、formula-pattern、formula-exception、button、VBA-event に型付き安定 ID を付ける。
  - 注釈は element ID を参照し、存在しない ID を孤立として報告する。
  - 数式パターン、例外式、VBA イベントの回答を該当要素へ織り込む。
  - 既存 range 注釈の移行方法を定義しテストする。
- 対象外: Excel オブジェクト全種類の完全な意味モデル。

- [ ] **Step 4: SL-004 を次の内容で作成する**

- Metadata: `status=proposed`、`priority=P1`、`type=enhancement`、`milestone=M1`、`depends_on=[SL-002, SL-003]`
- Touches: `src/sheetlens/model/ir.py`、`src/sheetlens/pipeline.py`、`src/sheetlens/renderers/machine.py`、`src/sheetlens/renderers/markdown.py`、`tests/test_machine.py`、`tests/test_markdown.py`、`tests/test_compile_e2e.py`
- 背景と根本原因: 意味層の正が Markdown にしかなく、注釈テキスト中の改行や見出しが文書構造として解釈される。
- 根拠: `src/sheetlens/renderers/markdown.py:15-35` と `:94-96` は注釈を無加工で挿入し、無害化はグリッドセル `:39-40` に限られる。
- 受け入れ条件:
  - 構造要素 ID と provenance を含む compiled 意味層 JSON を生成する。
  - Markdown は compiled データから生成し、見出し、blockquote、code fence を注釈から生成させない。
  - role、note、value に改行、`##`、`> ❓`、backtick、pipe を含むテストを追加する。
  - Markdown parser 上の正規見出し集合が注釈内容で変化しない。
- 対象外: 一般目的の prompt-injection 検出器。

- [ ] **Step 5: M1 追加による stale backlog を確認して再生成する**

Run: `uv run python scripts/check_project_state.py check`

Expected: FAIL only because `backlog.md` is stale

Run: `uv run python scripts/check_project_state.py render && uv run python scripts/check_project_state.py check`

Expected: render succeeds and check exits 0

- [ ] **Step 6: M1 課題をコミットする**

```bash
git add docs/project/items/SL-001-* docs/project/items/SL-002-* docs/project/items/SL-003-* docs/project/items/SL-004-* docs/project/backlog.md
git commit -m "docs: register semantic integrity backlog"
```

### Task 2: M2 構造抽出の完全性を登録する

**Files:**
- Create: `docs/project/items/SL-005-defined-name-validations.md`
- Create: `docs/project/items/SL-006-conditional-format-ir.md`
- Create: `docs/project/items/SL-007-cell-display-semantics.md`
- Create: `docs/project/items/SL-008-artifact-presence.md`
- Create: `docs/project/items/SL-009-structural-range.md`
- Create: `docs/project/items/SL-010-vml-buttons.md`
- Modify: `docs/project/backlog.md`

**Interfaces:**
- Produces: M2 の 6 課題

- [ ] **Step 1: SL-005 を次の内容で作成する**

- Metadata: `ready`、`P1`、`defect`、`M2`、依存なし
- Touches: `src/sheetlens/reader/features.py`、`src/sheetlens/reader/workbook.py`、`tests/test_features.py`
- 根本原因: `_resolve_list` は `=Choices` を現在シートのセル参照として扱い、解決失敗を空配列へ潰す。
- 根拠: `src/sheetlens/reader/features.py:4-23`、`src/sheetlens/reader/workbook.py:56-60`。有効な名前定義でも `choices=[]` を親監査で再現済み。
- 受け入れ条件: workbook scope と sheet-local scope、引用シート名を解決する。未解決名、INDIRECT、OFFSET は gap にする。各ケースのテストを追加する。
- 対象外: 任意の動的 Excel 式を完全評価すること。

- [ ] **Step 2: SL-006 を次の内容で作成する**

- Metadata: `ready`、`P1`、`defect`、`M2`、依存なし
- Touches: `src/sheetlens/model/ir.py`、`src/sheetlens/reader/features.py`、`tests/test_ir.py`、`tests/test_features.py`
- 根本原因: ConditionalFormat は式を 1 件しか保持せず、reader は先頭式だけを保存し、color scale 等の payload を捨てる。
- 根拠: `src/sheetlens/model/ir.py:21-26`、`src/sheetlens/reader/features.py:47-59`。between の第 2 式と color scale payload の欠落を親監査で再現済み。
- 受け入れ条件: formulas 配列、colorScale、dataBar、iconSet、dxf の type 別 payload を保存する。未対応型は gap にする。between、複数式 expression、全可視化型をテストする。
- 対象外: 条件付き書式の画面レンダリング。

- [ ] **Step 3: SL-007 を次の内容で作成する**

- Metadata: `ready`、`P1`、`enhancement`、`M2`、依存なし
- Touches: `src/sheetlens/model/ir.py`、`src/sheetlens/reader/workbook.py`、`src/sheetlens/renderers/markdown.py`、`tests/test_ir.py`、`tests/test_reader.py`、`tests/test_markdown.py`
- 根本原因: Cell は value と formula だけで、数値が百分率、通貨、日付、先頭ゼロ付きコードのどれかを表現できない。
- 根拠: `src/sheetlens/model/ir.py:8-11`、`src/sheetlens/reader/workbook.py:12-15`。
- 受け入れ条件: value_type、number_format、必要最小限の display_semantics を保持する。percentage、currency、date/time、leading-zero、Excel error の JSON と Markdown をテストする。
- 対象外: Excel の完全な見た目再現とフォント・罫線の全抽出。

- [ ] **Step 4: SL-008 を次の内容で作成する**

- Metadata: `ready`、`P1`、`enhancement`、`M2`、依存なし
- Touches: `src/sheetlens/model/ir.py`、`src/sheetlens/reader/workbook.py`、`src/sheetlens/renderers/machine.py`、`tests/test_reader.py`、`tests/test_machine.py`
- 根本原因: charts、drawings、pivots の存在を保持する IR がなく、「存在しない」と「未抽出」を区別できない。
- 根拠: `src/sheetlens/model/ir.py:53-61`、`docs/superpowers/specs/2026-07-07-sheetlens-design.md:198-204`。
- 受け入れ条件: シート別の artifact type、件数、OOXML part を保存する。詳細未対応は gap として manifest に出す。chart、image/shape、pivot part をテストする。
- 対象外: グラフ系列、図形レイアウト、ピボット定義の完全解析。

- [ ] **Step 5: SL-009 を次の内容で作成する**

- Metadata: `ready`、`P2`、`defect`、`M2`、依存なし
- Touches: `src/sheetlens/model/ir.py`、`src/sheetlens/reader/workbook.py`、`src/sheetlens/detectors/questions.py`、`tests/test_reader.py`、`tests/test_questions.py`
- 根本原因: used_range は値セルだけから求められ、空の結合・入力規則・条件付き書式を無視する。グループ化された非表示列は先頭キーだけ記録する。
- 根拠: `src/sheetlens/reader/workbook.py:37-38`、`:69`、`:72`。
- 受け入れ条件: content range と structural range を分離する。結合、入力規則、条件付き書式を structural range に含める。B:D のグループ非表示を全範囲として保存する。
- 対象外: 書式だけが無制限に設定されたシートの全セル展開。

- [ ] **Step 6: SL-010 を次の内容で作成する**

- Metadata: `ready`、`P2`、`defect`、`M2`、依存なし
- Touches: `src/sheetlens/model/ir.py`、`src/sheetlens/reader/buttons.py`、`tests/test_vba.py`
- 根本原因: VML macro は namespace prefix 固定の正規表現で抽出され、label と欠損 relationship を保持しない。
- 根拠: `src/sheetlens/reader/buttons.py:12`、`:32-43`、`src/sheetlens/model/ir.py:34-37`。
- 受け入れ条件: ElementTree で namespace URI により解析し、shape label と macro を対応付ける。別 prefix、entity、欠損 VML、複数ボタンをテストする。ActiveX は存在または gap を記録する。
- 対象外: ActiveX コントロールの完全なプロパティ解析。

- [ ] **Step 7: M2 を render/check してコミットする**

Run: `uv run python scripts/check_project_state.py render && uv run python scripts/check_project_state.py check`

Expected: both exit 0

```bash
git add docs/project/items/SL-005-* docs/project/items/SL-006-* docs/project/items/SL-007-* docs/project/items/SL-008-* docs/project/items/SL-009-* docs/project/items/SL-010-* docs/project/backlog.md
git commit -m "docs: register extraction fidelity backlog"
```

### Task 3: M3 分析・実行信頼性を登録する

**Files:**
- Create: `docs/project/items/SL-011-input-formula-regions.md`
- Create: `docs/project/items/SL-012-formula-dependency-parser.md`
- Create: `docs/project/items/SL-013-atomic-extract-cli-errors.md`
- Modify: `docs/project/backlog.md`

**Interfaces:**
- Produces: M3 の 3 課題

- [ ] **Step 1: SL-011 を次の内容で作成する**

- Metadata: `ready`、`P1`、`defect`、`M3`、依存なし
- Touches: `src/sheetlens/detectors/regions.py`、`src/sheetlens/detectors/questions.py`、`tests/test_regions.py`、`tests/test_questions.py`
- 根本原因: region 内に数式が 1 セルでもあると領域全体の input_source 質問を生成しない。
- 根拠: `src/sheetlens/detectors/questions.py:21-29`、`:52-56`、`src/sheetlens/detectors/regions.py:23-32`。
- 受け入れ条件: 手入力セルと数式セルを列または連結範囲で分離する。A:B 手入力、C 数式の表では A:B だけを質問対象にする。離れた表と header を誤結合しない。
- 対象外: AI による入力元の自動推定。

- [ ] **Step 2: SL-012 を次の内容で作成する**

- Metadata: `ready`、`P2`、`refactor`、`M3`、依存なし
- Touches: `src/sheetlens/detectors/formula_patterns.py`、`src/sheetlens/renderers/machine.py`、`src/sheetlens/model/ir.py`、`tests/test_formula_patterns.py`、`tests/test_machine.py`
- 根本原因: 数式正規化と依存検出が文字列正規表現中心で、lowercase、引用シート名、外部同名シート、defined name を誤分類する。
- 根拠: `src/sheetlens/detectors/formula_patterns.py:10-11`、`:28-55`、`src/sheetlens/renderers/machine.py:9-38`。
- 受け入れ条件: Excel tokenizer とセル位置基準の相対参照で正規化する。依存を source、target_workbook、target_sheet、target_range、unresolved の edge として保存する。外部同名シート、defined name、validation/CF 参照をテストする。
- 対象外: Excel 計算エンジンの実装。

- [ ] **Step 3: SL-013 を次の内容で作成する**

- Metadata: `ready`、`P2`、`refactor`、`M3`、依存なし
- Touches: `src/sheetlens/pipeline.py`、`src/sheetlens/cli.py`、`tests/test_extract_e2e.py`、`tests/test_compile_e2e.py`、`tests/test_check_e2e.py`、`tests/test_cli.py`
- 根本原因: extract は旧 structure を先に削除して複数ファイルを順次書き、compile/check は壊れた raw JSON や I/O 例外を統一した利用者向けエラーへ変換しない。
- 根拠: `src/sheetlens/pipeline.py:99-122`、`src/sheetlens/cli.py:39-43`、`:56-65`。
- 受け入れ条件: 一時ディレクトリへ全成果物を生成・検証後に置換する。途中失敗時に旧成果物と annotations を保持する。JSON、Pydantic、Unicode、OSError をパスと復旧方法付きエラーに変換する。
- 対象外: 長時間処理の分散トランザクションと自動 retry。

- [ ] **Step 4: M3 を render/check してコミットする**

Run: `uv run python scripts/check_project_state.py render && uv run python scripts/check_project_state.py check`

Expected: both exit 0

```bash
git add docs/project/items/SL-011-* docs/project/items/SL-012-* docs/project/items/SL-013-* docs/project/backlog.md
git commit -m "docs: register analysis reliability backlog"
```

### Task 4: M4 品質保証を登録する

**Files:**
- Create: `docs/project/items/SL-014-real-xlsm-windows.md`
- Create: `docs/project/items/SL-015-reproducible-evaluation.md`
- Create: `docs/project/items/SL-016-golden-ci-quality.md`
- Create: `docs/project/items/SL-017-package-repository-hygiene.md`
- Modify: `docs/project/backlog.md`

**Interfaces:**
- Produces: M4 の 4 課題と全 17 件の backlog

- [ ] **Step 1: SL-014 を次の内容で作成する**

- Metadata: `ready`、`P1`、`quality`、`M4`、依存なし
- Touches: `tests/fixtures`、`tests/test_vba.py`、`tests/test_extract_e2e.py`、`.github/workflows`、`README.md`
- 根本原因: 想定環境は Windows と実 xlsm だが、VBA 正常系は parser mock、ボタンは最小手製 ZIP で、本番形式を通していない。
- 根拠: `docs/superpowers/specs/2026-07-07-sheetlens-design.md:25`、`README.md:110`、`tests/test_vba.py:37-129`。
- 受け入れ条件: 再配布可能な最小 xlsm fixture を追加する。VBA module、event、フォームボタン、文字コード、gap を E2E 検証する。Windows CI で成功する。業務 PC の受入結果を記録する。
- 対象外: 実業務ファイルのリポジトリ保存。

- [ ] **Step 2: SL-015 を次の内容で作成する**

- Metadata: `proposed`、`P1`、`quality`、`M4`、`depends_on=[SL-001, SL-003]`
- Touches: `eval`、`tests/test_eval_dummy.py`、`README.md`
- 根本原因: A/B 評価は手動セッションと主観的な「明確に上回る」判定で、モデル、prompt、試行数、rubric、閾値を再現できない。
- 根拠: `eval/README.md:10-20`、`README.md:112`、`eval/questions.yaml:5`。
- 受け入れ条件: 評価 manifest、固定 prompt、モデル設定、複数試行、rubric、閾値、結果 JSON/Markdown schema を定義する。構造層だけでなく意味層 QA と負例を含める。欠損回答も採点する。
- 対象外: 特定 LLM ベンダーへの固定と本番業務データの収集。

- [ ] **Step 3: SL-016 を次の内容で作成する**

- Metadata: `ready`、`P2`、`quality`、`M4`、依存なし
- Touches: `pyproject.toml`、`.github/workflows`、`tests/golden`、`tests/test_markdown.py`、`tests/test_machine.py`
- 根本原因: CI、型チェック、coverage gate、設計書が要求する出力全体の golden test がない。
- 根拠: `pyproject.toml:17-30`、`docs/superpowers/specs/2026-07-07-sheetlens-design.md:187-196`、`tests/test_markdown.py:26`。
- 受け入れ条件: Ubuntu/Windows と Python 3.12-3.14 の CI を追加する。lock、pytest、Ruff、型、coverage、build、wheel smoke を検証する。代表 fixture の raw、manifest、Markdown の決定的 golden を追加する。新規品質依存は事前承認を得る。
- 対象外: すべての Python/OS 組み合わせと100% coverage。

- [ ] **Step 4: SL-017 を次の内容で作成する**

- Metadata: `ready`、`P3`、`quality`、`M4`、依存なし
- Touches: `pyproject.toml`、`.gitignore`、`README.md`
- 根本原因: 配布メタデータと sdist 境界が未定義で、生成 xlsx、`.sheetlens/`、build、coverage 成果物の ignore が不足する。
- 根拠: `pyproject.toml:1-24`、`.gitignore:1-4`、`README.md:92`。
- 受け入れ条件: readme、license、authors、URLs、classifiers を定義する。sdist include/exclude と wheel smoke を検証する。生成 Excel、`*.sheetlens/`、dist、build、coverage を ignore し、実業務 Excel の持込禁止を文書化する。
- 対象外: PyPI 公開とリリース自動化。

- [ ] **Step 5: M4 を render/check してコミットする**

Run: `uv run python scripts/check_project_state.py render && uv run python scripts/check_project_state.py check`

Expected: both exit 0 and backlog contains 17 rows

```bash
git add docs/project/items/SL-014-* docs/project/items/SL-015-* docs/project/items/SL-016-* docs/project/items/SL-017-* docs/project/backlog.md
git commit -m "docs: register quality assurance backlog"
```

### Task 5: 初期 Backlog 全体を検証する

**Files:**
- Verify: `docs/project/items/*.md`
- Verify: `docs/project/backlog.md`
- Verify: `docs/project/roadmap.md`

**Interfaces:**
- Consumes: 全 17 課題
- Produces: 実装着手可能な検証済み backlog

- [ ] **Step 1: ID、行数、状態を検査する**

Run:

```bash
test "$(find docs/project/items -maxdepth 1 -name 'SL-*.md' | wc -l)" -eq 17
test "$(rg -c '^\| \[SL-[0-9]{3}\]' docs/project/backlog.md)" -eq 17
uv run python scripts/check_project_state.py check
```

Expected: both counts are 17 and check exits 0

- [ ] **Step 2: next が eligible な ready 課題だけを表示することを確認する**

Run: `uv run python scripts/check_project_state.py next`

Expected: output includes 初期並行候補の SL-001、SL-005、SL-014, and excludes
dependency-bound proposed の SL-002、SL-003、SL-004、SL-015。ほかの依存なし `ready` 課題も
eligible として表示され得るため、候補表示と実際の選定を区別する。未完了・欠損・重複
dependency の eligibility は Foundation Task 5 の focused tests で検証済みであること。

- [ ] **Step 3: リポジトリ全体を検証する**

Run:

```bash
uv run ruff check .
uv run pytest
git diff --check
git status --short
```

Expected: Ruff clean、全テスト PASS、diff check clean、意図した管理ファイルだけが変更対象

- [ ] **Step 4: 最終検証結果をコミットする**

管理ファイルに追加修正がある場合だけコミットする。変更がなければ新しい空コミットは作らない。

## Plan Completion Check

- [ ] 17 件すべてが監査所見の根本原因、根拠、受け入れ条件、対象外を持つことを確認する。
- [ ] `rg -n 'T[B]D|T[O]DO|F[I]XME|implement[ ]later|fill[ ]in' docs/project/items` が該当なしであることを確認する。
- [ ] `uv run python scripts/check_project_state.py render && uv run python scripts/check_project_state.py check` を実行する。
- [ ] `uv run ruff check . && uv run pytest` を実行する。
- [ ] backlog が 17 行で、`next` が eligible な `ready` 課題だけを表示することを確認する。
