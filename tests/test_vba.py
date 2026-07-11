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

SHEET_XML = """<?xml version="1.0"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <legacyDrawing r:id="rId2"/>
</worksheet>"""

VML = """<xml xmlns:v="urn:schemas-microsoft-com:vml"
 xmlns:x="urn:schemas-microsoft-com:office:excel">
 <v:shape id="submit"><v:textbox><div>見積を登録</div></v:textbox>
 <x:ClientData ObjectType="Button">
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
        z.writestr("xl/worksheets/sheet1.xml", SHEET_XML)
        z.writestr("xl/worksheets/_rels/sheet1.xml.rels", SHEET_RELS)
        z.writestr("xl/drawings/vmlDrawing1.vml", VML)
    assert extract_buttons(path) == [
        ir.ButtonLink(
            sheet="見積入力",
            label="見積を登録",
            macro="Module1.RegisterEstimate",
        )
    ]


def test_extract_buttons_uses_namespace_uris_and_keeps_shape_pairing(tmp_path):
    path = tmp_path / "buttons.xlsm"
    vml = """<xml xmlns:vm="urn:schemas-microsoft-com:vml"
     xmlns:xl="urn:schemas-microsoft-com:office:excel">
     <vm:shape id="first"><vm:textbox><div>Save &amp; Close</div></vm:textbox>
      <xl:ClientData ObjectType="Button"><xl:FmlaMacro>Module1.Save</xl:FmlaMacro></xl:ClientData>
     </vm:shape>
     <vm:shape id="second"><vm:textbox><div> Second\n Button </div></vm:textbox>
      <xl:ClientData ObjectType="Button"><xl:FmlaMacro>Module1.Second</xl:FmlaMacro></xl:ClientData>
     </vm:shape>
     <vm:shape id="broken"><vm:textbox><div>Broken Button</div></vm:textbox>
      <xl:ClientData ObjectType="Button"/>
     </vm:shape>
    </xml>"""
    _write_zip(
        path,
        {
            "xl/workbook.xml": WORKBOOK_XML,
            "xl/_rels/workbook.xml.rels": WORKBOOK_RELS,
            "xl/worksheets/sheet1.xml": SHEET_XML,
            "xl/worksheets/_rels/sheet1.xml.rels": SHEET_RELS,
            "xl/drawings/vmlDrawing1.vml": vml,
        },
    )
    gaps = []

    assert extract_buttons(path, extraction_gaps=gaps) == [
        ir.ButtonLink(sheet="見積入力", label="Save & Close", macro="Module1.Save"),
        ir.ButtonLink(sheet="見積入力", label="Second Button", macro="Module1.Second"),
    ]
    assert gaps == ["見積入力: VML button Broken Button (broken) のmacroがありません"]


def test_extract_buttons_records_vml_relationship_and_xml_gaps(tmp_path):
    unresolved = tmp_path / "unresolved.xlsm"
    _write_zip(
        unresolved,
        {
            "xl/workbook.xml": WORKBOOK_XML,
            "xl/_rels/workbook.xml.rels": WORKBOOK_RELS,
            "xl/worksheets/sheet1.xml": SHEET_XML.replace("rId2", "rIdMissing"),
            "xl/worksheets/_rels/sheet1.xml.rels": SHEET_RELS,
        },
    )
    gaps = []
    assert extract_buttons(unresolved, extraction_gaps=gaps) == []
    assert gaps == ["見積入力: VML relationship rIdMissing は未解決です"]

    malformed = tmp_path / "malformed.xlsm"
    _write_zip(
        malformed,
        {
            "xl/workbook.xml": WORKBOOK_XML,
            "xl/_rels/workbook.xml.rels": WORKBOOK_RELS,
            "xl/worksheets/sheet1.xml": SHEET_XML,
            "xl/worksheets/_rels/sheet1.xml.rels": SHEET_RELS,
            "xl/drawings/vmlDrawing1.vml": "<xml><broken></xml>",
        },
    )
    gaps = []
    assert extract_buttons(malformed, extraction_gaps=gaps) == []
    assert len(gaps) == 1
    assert gaps[0].startswith("見積入力: VML part xl/drawings/vmlDrawing1.vml のXMLが不正")


def test_duplicate_vml_relationship_id_fails_closed(tmp_path):
    path = tmp_path / "duplicate-vml-rel.xlsm"
    duplicate_rels = SHEET_RELS.replace(
        "</Relationships>",
        """<Relationship Id="rId2"
         Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing"
         Target="../drawings/other.vml"/></Relationships>""",
    )
    _write_zip(
        path,
        {
            "xl/workbook.xml": WORKBOOK_XML,
            "xl/_rels/workbook.xml.rels": WORKBOOK_RELS,
            "xl/worksheets/sheet1.xml": SHEET_XML,
            "xl/worksheets/_rels/sheet1.xml.rels": duplicate_rels,
            "xl/drawings/vmlDrawing1.vml": VML,
            "xl/drawings/other.vml": VML,
        },
    )
    gaps = []

    assert extract_buttons(path, extraction_gaps=gaps) == []
    assert gaps == ["見積入力: VML relationship rId2 のIDが重複しています"]


def test_extract_buttons_records_logical_activex_controls_once(tmp_path):
    path = tmp_path / "activex.xlsm"
    sheet_xml = """<worksheet
     xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
     xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
     xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">
     <controls>
      <mc:AlternateContent>
       <mc:Choice Requires="x14"><control shapeId="1" name="Run" r:id="rId3"/></mc:Choice>
       <mc:Fallback><control shapeId="1" name="Run" r:id="rId3"/></mc:Fallback>
      </mc:AlternateContent>
      <control shapeId="2" name="Missing Id"/>
     </controls>
    </worksheet>"""
    sheet_rels = """<Relationships
     xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
     <Relationship Id="rId3"
      Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/control"
      Target="../activeX/activeX1.xml"/>
     <Relationship Id="rIdOrphan"
      Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/control"
      Target="../activeX/orphan.xml"/>
    </Relationships>"""
    _write_zip(
        path,
        {
            "xl/workbook.xml": WORKBOOK_XML,
            "xl/_rels/workbook.xml.rels": WORKBOOK_RELS,
            "xl/worksheets/sheet1.xml": sheet_xml,
            "xl/worksheets/_rels/sheet1.xml.rels": sheet_rels,
            "xl/activeX/activeX1.xml": "<ocx/>",
            "xl/activeX/orphan.xml": "<ocx/>",
        },
    )
    gaps = []

    assert extract_buttons(path, extraction_gaps=gaps) == []
    assert gaps == [
        "見積入力: ActiveX control Missing Id はrelationship IDがありません",
        "見積入力: ActiveX control 1件の詳細抽出は未対応です",
    ]


def test_duplicate_activex_relationship_id_fails_closed(tmp_path):
    path = tmp_path / "duplicate-activex-rel.xlsm"
    sheet_xml = """<worksheet
     xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
     xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
     <controls><control shapeId="1" name="Run" r:id="rId3"/></controls>
    </worksheet>"""
    sheet_rels = """<Relationships
     xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
     <Relationship Id="rId3"
      Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/control"
      Target="../activeX/activeX1.xml"/>
     <Relationship Id="rId3"
      Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/control"
      Target="../activeX/activeX2.xml"/>
    </Relationships>"""
    _write_zip(
        path,
        {
            "xl/workbook.xml": WORKBOOK_XML,
            "xl/_rels/workbook.xml.rels": WORKBOOK_RELS,
            "xl/worksheets/sheet1.xml": sheet_xml,
            "xl/worksheets/_rels/sheet1.xml.rels": sheet_rels,
            "xl/activeX/activeX1.xml": "<ocx/>",
            "xl/activeX/activeX2.xml": "<ocx/>",
        },
    )
    gaps = []

    assert extract_buttons(path, extraction_gaps=gaps) == []
    assert gaps == ["見積入力: ActiveX relationship rId3 のIDが重複しています"]


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
            "xl/worksheets/sheet1.xml": SHEET_XML,
        },
    )
    assert extract_buttons(missing_sheet_rels) == []

    missing_vml = tmp_path / "missing-vml.xlsm"
    _write_zip(
        missing_vml,
        {
            "xl/workbook.xml": WORKBOOK_XML,
            "xl/_rels/workbook.xml.rels": WORKBOOK_RELS,
            "xl/worksheets/sheet1.xml": SHEET_XML,
            "xl/worksheets/_rels/sheet1.xml.rels": SHEET_RELS,
        },
    )
    gaps = []
    assert extract_buttons(missing_vml, extraction_gaps=gaps) == []
    assert gaps == ["見積入力: VML part xl/drawings/vmlDrawing1.vml が見つかりません"]
