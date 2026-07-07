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
