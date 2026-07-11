# Real XLSM fixture provenance

These workbooks are unmodified upstream test/example files. SheetLens never executes their
macros; the tests only perform static package and VBA-source extraction.

## `openpyxl-vba-test.xlsm`

- Purpose: real VBA standard module, `Workbook_Open` event, form-control button, and
  deterministic unsupported-drawing gaps.
- Upstream: `ericgazoni/openpyxl`, `openpyxl/tests/test_data/reader/vba-test.xlsm`.
- Fixed revision: `c55988e4904d4337ce4c35ab8b7dc305bca9de23`.
- Source: <https://raw.githubusercontent.com/ericgazoni/openpyxl/c55988e4904d4337ce4c35ab8b7dc305bca9de23/openpyxl/tests/test_data/reader/vba-test.xlsm>
- SHA-256: `39ab44eb0d0725cf66baee054da963ae8292ecb41212062942fac14ce3cc59c1`.
- Macro behavior: `Workbook_Open` hides the `Scratch` sheet; other modules manipulate workbook
  data and display forms. Do not execute this fixture; it is for static extraction only.
- License: MIT, copyright 2010 openpyxl. The complete repository-wide notice is included as
  `LICENSE.openpyxl.txt`.

## `openxml-sdk-macro.xlsm`

- Purpose: real VBA project whose module name is the non-ASCII string `模块1`.
- Upstream: `dotnet/Open-XML-SDK`,
  `test/DocumentFormat.OpenXml.Tests.Assets/assets/TestDataStorage/v2FxTestFiles/spreadsheet/macro.xlsm`.
- Fixed revision: `c411da60259d5d63d4e05e198c66d07ee7700621`.
- Source: <https://raw.githubusercontent.com/dotnet/Open-XML-SDK/c411da60259d5d63d4e05e198c66d07ee7700621/test/DocumentFormat.OpenXml.Tests.Assets/assets/TestDataStorage/v2FxTestFiles/spreadsheet/macro.xlsm>
- SHA-256: `6dd35cbb936ce4990c63d5747e43a363e1502a58f17c5f2ab6795849265a5d9f`.
- Benign behavior: writes the values 1, 2, 3 and their sum into cells A1:A4.
- License: MIT, copyright .NET Foundation and Contributors. The complete notice is included as
  `LICENSE.openxml-sdk.txt`.
