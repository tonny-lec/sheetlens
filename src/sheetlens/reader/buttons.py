from __future__ import annotations

import posixpath
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from sheetlens.model import ir

_SSML_NAMESPACES = frozenset(
    {
        "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "http://purl.oclc.org/ooxml/spreadsheetml/main",
        "https://purl.oclc.org/ooxml/spreadsheetml/main",
    }
)
_OFFICE_REL_NAMESPACES = frozenset(
    {
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "http://purl.oclc.org/ooxml/officeDocument/relationships",
        "https://purl.oclc.org/ooxml/officeDocument/relationships",
    }
)
_PACKAGE_REL_NAMESPACES = frozenset(
    {"http://schemas.openxmlformats.org/package/2006/relationships"}
)
_VML_NAMESPACES = frozenset({"urn:schemas-microsoft-com:vml"})
_EXCEL_NAMESPACES = frozenset({"urn:schemas-microsoft-com:office:excel"})
_RELATIONSHIP_TYPES = {
    kind: frozenset(f"{base}/{kind}" for base in _OFFICE_REL_NAMESPACES)
    for kind in ("worksheet", "vmlDrawing", "control")
}


@dataclass(frozen=True)
class _Relationship:
    type: str | None
    target: str | None
    external: bool


@dataclass(frozen=True)
class _RelationshipIndex:
    by_id: dict[str, _Relationship]
    duplicate_ids: frozenset[str]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(tag: str) -> str | None:
    if not tag.startswith("{") or "}" not in tag:
        return None
    return tag[1:].split("}", 1)[0]


def _is_qname(tag: str, namespaces: frozenset[str], *names: str) -> bool:
    return _namespace(tag) in namespaces and _local_name(tag) in names


def _relationship_id(node: ET.Element) -> str | None:
    return next(
        (
            value
            for attribute, value in node.attrib.items()
            if _is_qname(attribute, _OFFICE_REL_NAMESPACES, "id")
        ),
        None,
    )


def _relationships_part(source_part: str) -> str:
    directory, filename = posixpath.split(source_part)
    return posixpath.join(directory, "_rels", f"{filename}.rels")


def _load_relationships(
    package: zipfile.ZipFile,
    source_part: str,
) -> _RelationshipIndex:
    part = _relationships_part(source_part)
    if part not in package.namelist():
        return _RelationshipIndex({}, frozenset())
    root = ET.fromstring(package.read(part))
    relationships: dict[str, _Relationship] = {}
    duplicate_ids: set[str] = set()
    for node in root:
        if not _is_qname(node.tag, _PACKAGE_REL_NAMESPACES, "Relationship"):
            continue
        rel_id = node.get("Id")
        if not rel_id:
            continue
        if rel_id in relationships or rel_id in duplicate_ids:
            relationships.pop(rel_id, None)
            duplicate_ids.add(rel_id)
            continue
        relationships[rel_id] = _Relationship(
            type=node.get("Type"),
            target=node.get("Target"),
            external=node.get("TargetMode", "").lower() == "external",
        )
    return _RelationshipIndex(relationships, frozenset(duplicate_ids))


def _resolve_target(source_part: str, target: str) -> str | None:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return None
    decoded = unquote(parsed.path)
    if not decoded or "\\" in decoded or "\x00" in decoded:
        return None
    if decoded.startswith("/"):
        resolved = posixpath.normpath(decoded.lstrip("/"))
    else:
        resolved = posixpath.normpath(
            posixpath.join(posixpath.dirname(source_part), decoded)
        )
    if resolved in ("", ".", "..") or resolved.startswith("../"):
        return None
    return resolved


def _worksheet_parts(package: zipfile.ZipFile) -> list[tuple[str, str]]:
    names = set(package.namelist())
    workbook_part = "xl/workbook.xml"
    if workbook_part not in names:
        return []
    relationships = _load_relationships(package, workbook_part)
    root = ET.fromstring(package.read(workbook_part))
    worksheets: list[tuple[str, str]] = []
    for sheet in root.iter():
        if not _is_qname(sheet.tag, _SSML_NAMESPACES, "sheet"):
            continue
        sheet_name = sheet.get("name")
        rel_id = _relationship_id(sheet)
        relationship = relationships.by_id.get(rel_id) if rel_id else None
        if (
            not sheet_name
            or relationship is None
            or relationship.type not in _RELATIONSHIP_TYPES["worksheet"]
            or relationship.external
            or not relationship.target
        ):
            continue
        sheet_part = _resolve_target(workbook_part, relationship.target)
        if sheet_part and sheet_part in names:
            worksheets.append((sheet_name, sheet_part))
    return worksheets


def _vml_part(
    package_parts: set[str],
    sheet_name: str,
    sheet_part: str,
    rel_id: str | None,
    relationship: _Relationship | None,
    duplicate_rel_id: bool,
    gaps: list[str],
) -> str | None:
    label = rel_id or "(r:id なし)"
    if duplicate_rel_id:
        gaps.append(f"{sheet_name}: VML relationship {label} のIDが重複しています")
        return None
    if relationship is None:
        gaps.append(f"{sheet_name}: VML relationship {label} は未解決です")
        return None
    if relationship.type not in _RELATIONSHIP_TYPES["vmlDrawing"]:
        gaps.append(
            f"{sheet_name}: VML relationship {label} の型は未対応です"
        )
        return None
    if relationship.external:
        gaps.append(f"{sheet_name}: VML relationship {label} は外部Targetです")
        return None
    if not relationship.target:
        gaps.append(f"{sheet_name}: VML relationship {label} のTargetがありません")
        return None
    part = _resolve_target(sheet_part, relationship.target)
    if part is None:
        gaps.append(f"{sheet_name}: VML relationship {label} のTargetが不正です")
        return None
    if part not in package_parts:
        gaps.append(f"{sheet_name}: VML part {part} が見つかりません")
        return None
    return part


def _shape_label(shape: ET.Element) -> str | None:
    textbox = next(
        (
            node
            for node in shape.iter()
            if _is_qname(node.tag, _VML_NAMESPACES, "textbox")
        ),
        None,
    )
    if textbox is None:
        return None
    label = " ".join("".join(textbox.itertext()).split())
    return label or None


def _buttons_from_vml(
    root: ET.Element,
    sheet_name: str,
    gaps: list[str],
) -> list[ir.ButtonLink]:
    buttons: list[ir.ButtonLink] = []
    for shape in root.iter():
        if not _is_qname(shape.tag, _VML_NAMESPACES, "shape"):
            continue
        client_data = next(
            (
                node
                for node in shape.iter()
                if _is_qname(node.tag, _EXCEL_NAMESPACES, "ClientData")
                and node.get("ObjectType") == "Button"
            ),
            None,
        )
        if client_data is None:
            continue
        label = _shape_label(shape)
        macro_node = next(
            (
                node
                for node in client_data.iter()
                if _is_qname(node.tag, _EXCEL_NAMESPACES, "FmlaMacro")
            ),
            None,
        )
        macro = (
            None
            if macro_node is None or macro_node.text is None
            else macro_node.text.strip()
        )
        if not macro:
            shape_id = shape.get("id")
            identity = label or "(labelなし)"
            if shape_id:
                identity = f"{identity} ({shape_id})"
            gaps.append(f"{sheet_name}: VML button {identity} のmacroがありません")
            continue
        buttons.append(ir.ButtonLink(sheet=sheet_name, label=label, macro=macro))
    return buttons


def _record_activex_gaps(
    package_parts: set[str],
    sheet_name: str,
    sheet_part: str,
    root: ET.Element,
    relationships: _RelationshipIndex,
    gaps: list[str],
) -> None:
    controls: dict[str, tuple[str | None, str | None]] = {}
    for node in root.iter():
        if not _is_qname(node.tag, _SSML_NAMESPACES, "control"):
            continue
        rel_id = _relationship_id(node)
        name = node.get("name") or node.get("shapeId") or "(名前なし)"
        if not rel_id:
            gaps.append(
                f"{sheet_name}: ActiveX control {name} はrelationship IDがありません"
            )
            continue
        identity = (node.get("shapeId"), node.get("name"))
        previous = controls.get(rel_id)
        if previous is not None and previous != identity:
            gaps.append(
                f"{sheet_name}: control relationship {rel_id} の参照情報が矛盾しています"
            )
            continue
        controls[rel_id] = identity

    activex_count = 0
    for rel_id in controls:
        if rel_id in relationships.duplicate_ids:
            gaps.append(
                f"{sheet_name}: ActiveX relationship {rel_id} のIDが重複しています"
            )
            continue
        relationship = relationships.by_id.get(rel_id)
        if relationship is None:
            gaps.append(f"{sheet_name}: control relationship {rel_id} は未解決です")
            continue
        if relationship.type not in _RELATIONSHIP_TYPES["control"]:
            continue
        if relationship.external or not relationship.target:
            gaps.append(f"{sheet_name}: ActiveX relationship {rel_id} のTargetが不正です")
            continue
        part = _resolve_target(sheet_part, relationship.target)
        if part is None or part not in package_parts:
            gaps.append(f"{sheet_name}: ActiveX relationship {rel_id} の参照先がありません")
            continue
        activex_count += 1
    if activex_count:
        gaps.append(
            f"{sheet_name}: ActiveX control {activex_count}件の詳細抽出は未対応です"
        )


def extract_buttons(
    path: Path,
    extraction_gaps: list[str] | None = None,
) -> list[ir.ButtonLink]:
    gaps = [] if extraction_gaps is None else extraction_gaps
    buttons: list[ir.ButtonLink] = []
    with zipfile.ZipFile(path) as package:
        package_parts = set(package.namelist())
        for sheet_name, sheet_part in _worksheet_parts(package):
            try:
                sheet_root = ET.fromstring(package.read(sheet_part))
            except (KeyError, ET.ParseError):
                continue
            relationships = _load_relationships(package, sheet_part)
            _record_activex_gaps(
                package_parts,
                sheet_name,
                sheet_part,
                sheet_root,
                relationships,
                gaps,
            )
            parsed_vml_parts: set[str] = set()
            for node in sheet_root.iter():
                if not _is_qname(node.tag, _SSML_NAMESPACES, "legacyDrawing"):
                    continue
                rel_id = _relationship_id(node)
                part = _vml_part(
                    package_parts,
                    sheet_name,
                    sheet_part,
                    rel_id,
                    relationships.by_id.get(rel_id) if rel_id else None,
                    rel_id in relationships.duplicate_ids if rel_id else False,
                    gaps,
                )
                if part is None or part in parsed_vml_parts:
                    continue
                parsed_vml_parts.add(part)
                try:
                    root = ET.fromstring(package.read(part))
                except ET.ParseError as exc:
                    gaps.append(f"{sheet_name}: VML part {part} のXMLが不正 ({exc})")
                    continue
                buttons.extend(_buttons_from_vml(root, sheet_name, gaps))
    return buttons
