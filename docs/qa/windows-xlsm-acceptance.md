# Windows XLSM acceptance

This procedure records the SL-014 acceptance result on a representative business PC. It does
not enable or execute workbook macros; SheetLens statically reads the packages.

## Preconditions

- Windows business PC representative of the intended deployment environment.
- Python 3.12+ and uv available.
- A clean checkout of the candidate SheetLens commit.

## Procedure

Run these commands in PowerShell from the repository root:

```powershell
$Evidence = Join-Path $env:TEMP "sheetlens-xlsm-acceptance.txt"
Start-Transcript -Path $Evidence -Force
git rev-parse HEAD
[System.Environment]::OSVersion.VersionString
uv --version
uv sync --locked
uv run python --version
uv run --frozen pytest tests/test_xlsm_e2e.py -q
$Output = Join-Path $env:TEMP "sheetlens-xlsm-acceptance"
Remove-Item -Recurse -Force $Output -ErrorAction SilentlyContinue
uv run --frozen sheetlens extract tests/fixtures/xlsm/openpyxl-vba-test.xlsm --out $Output
uv run --frozen sheetlens check $Output
Stop-Transcript
Write-Output "Evidence: $Evidence"
```

Confirm all of the following:

- pytest reports four passed tests.
- `extract` reports the generated project path without a traceback.
- `$Output\structure\raw.json` contains `Calculations.bas`, `ThisWorkbook.cls`, and the
  `Scratch` button mapping.
- `$Output\questions.md` contains `ThisWorkbook.cls.Workbook_Open` and
  `[0]!Button1_Click`.
- `check` completes and reports the unanswered-question count.

## Result

Status: **deferred — user-approved**

Reason: on 2026-07-11 the user confirmed that the current PC cannot perform the Windows CI or
business-PC checks and approved treating them as lower-priority follow-up work. No successful
run is claimed, and the fields below intentionally remain unobserved.

| Field | Value |
|---|---|
| Date and timezone | not observed |
| Candidate commit | not observed |
| Windows edition/build | not observed |
| Python version | not observed |
| uv version | not observed |
| Operator | not observed |
| Focused pytest result | not run on business PC |
| CLI extract/check result | not run on business PC |
| Notes | Deferred by explicit user approval on 2026-07-11 |

Replace the unobserved values only after a future real run; do not infer or fabricate them.
