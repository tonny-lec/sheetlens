# Real XLSM Windows E2E Implementation Plan

**Goal:** Verify SheetLens against redistributable Excel-produced `.xlsm` packages on Windows and provide an auditable business-PC acceptance path.

**Architecture:** Vendor two small, immutable upstream fixtures with provenance and hashes. Exercise the complete `read_workbook()` and CLI extraction paths without mocks. Run only the focused XLSM suite in a Windows workflow so SL-014 does not absorb the broad CI matrix owned by SL-016.

**Tech Stack:** Python 3.12, oletools, openpyxl, pytest, uv, GitHub Actions Windows runner.

## Constraints

- Do not generate a pretend VBA project or depend on immature VBA-writing tooling.
- Keep each upstream binary byte-for-byte identical to its fixed revision.
- Record source URL, source commit, license, SHA-256, expected benign macro behavior, and test purpose.
- Never execute the fixture macros; SheetLens performs static extraction only.
- Keep Windows CI focused on the real XLSM tests; Ubuntu/Windows version matrices remain SL-016.
- Do not claim Windows CI or business-PC success without an actual run and recorded evidence.
- Do not push without explicit user authorization.

## Tasks

- [x] Vendor the openpyxl event/button fixture and Open XML SDK encoding fixture with provenance.
- [x] Add real-file E2E tests for VBA module, event question, form button, non-ASCII module name, known gaps, and CLI output.
- [x] Add a focused Windows GitHub Actions workflow using the locked environment.
- [x] Add a business-PC acceptance procedure and result template; update README limitations.
- [x] Run focused tests, the full required verification set, and defect-finding review.
- [x] Record the user-approved deferment of Windows CI and business-PC execution without claiming success.
