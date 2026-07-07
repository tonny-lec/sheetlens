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


def _write_zip(path, parts):
    with zipfile.ZipFile(path, "w") as z:
        for name, content in parts.items():
            z.writestr(name, content)


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


def test_extract_vba_no_macros_detected(tmp_path, monkeypatch):
    class FakeParser:
        def __init__(self, _):
            pass

        def detect_vba_macros(self):
            return False

        def extract_macros(self):
            raise AssertionError("extract_macros should not be called")

        def close(self):
            pass

    import sheetlens.reader.vba as vba_mod

    monkeypatch.setattr(vba_mod, "VBA_Parser", FakeParser)
    path = tmp_path / "macro.xlsm"
    path.write_bytes(b"dummy")
    assert extract_vba(path) == []


def test_extract_vba_with_mocked_parser(tmp_path, monkeypatch):
    class FakeParser:
        def __init__(self, _):
            pass

        def detect_vba_macros(self):
            return True

        def extract_macros(self):
            yield ("f", "s", "VBA/Module1.bas", "Sub RegisterEstimate()\nEnd Sub")

        def close(self):
            pass

    import sheetlens.reader.vba as vba_mod

    monkeypatch.setattr(vba_mod, "VBA_Parser", FakeParser)
    path = tmp_path / "macro.xlsm"
    path.write_bytes(b"dummy")
    mods = extract_vba(path)
    assert mods == [ir.VbaModule(name="Module1.bas", code="Sub RegisterEstimate()\nEnd Sub")]


def test_extract_buttons_tolerates_missing_parts(tmp_path):
    missing_workbook = tmp_path / "missing-workbook.xlsm"
    _write_zip(
        missing_workbook,
        {
            "xl/_rels/workbook.xml.rels": WORKBOOK_RELS,
        },
    )
    assert extract_buttons(missing_workbook) == []

    missing_sheet_rels = tmp_path / "missing-sheet-rels.xlsm"
    _write_zip(
        missing_sheet_rels,
        {
            "xl/workbook.xml": WORKBOOK_XML,
            "xl/_rels/workbook.xml.rels": WORKBOOK_RELS,
            "xl/worksheets/sheet1.xml": "<worksheet/>",
        },
    )
    assert extract_buttons(missing_sheet_rels) == []

    missing_vml = tmp_path / "missing-vml.xlsm"
    _write_zip(
        missing_vml,
        {
            "xl/workbook.xml": WORKBOOK_XML,
            "xl/_rels/workbook.xml.rels": WORKBOOK_RELS,
            "xl/worksheets/sheet1.xml": "<worksheet/>",
            "xl/worksheets/_rels/sheet1.xml.rels": SHEET_RELS,
        },
    )
    assert extract_buttons(missing_vml) == []
