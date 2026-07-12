from __future__ import annotations

import posixpath
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from sheetlens.model import ir

ArtifactType = Literal["chart", "image", "shape", "pivot"]
_TYPE_ORDER: tuple[ArtifactType, ...] = ("chart", "image", "shape", "pivot")
_SSML_NAMESPACES = frozenset(
    {
        "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "http://purl.oclc.org/ooxml/spreadsheetml/main",
        "https://purl.oclc.org/ooxml/spreadsheetml/main",
    }
)
_XDR_NAMESPACES = frozenset(
    {
        "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
        "http://purl.oclc.org/ooxml/drawingml/spreadsheetDrawing",
        "https://purl.oclc.org/ooxml/drawingml/spreadsheetDrawing",
    }
)
_DML_NAMESPACES = frozenset(
    {
        "http://schemas.openxmlformats.org/drawingml/2006/main",
        "http://purl.oclc.org/ooxml/drawingml/main",
        "https://purl.oclc.org/ooxml/drawingml/main",
    }
)
_CHART_NAMESPACES = frozenset(
    {
        "http://schemas.openxmlformats.org/drawingml/2006/chart",
        "http://purl.oclc.org/ooxml/drawingml/chart",
        "https://purl.oclc.org/ooxml/drawingml/chart",
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
_MC_NAMESPACES = frozenset(
    {"http://schemas.openxmlformats.org/markup-compatibility/2006"}
)
_RELATIONSHIP_TYPES = {
    kind: frozenset(
        f"{base}/{kind}"
        for base in _OFFICE_REL_NAMESPACES
    )
    for kind in ("worksheet", "chartsheet", "drawing", "pivotTable", "chart", "image")
}


@dataclass(frozen=True)
class _Relationship:
    id: str
    type: str
    target: str
    external: bool


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(tag: str) -> str | None:
    if not tag.startswith("{") or "}" not in tag:
        return None
    return tag[1:].split("}", 1)[0]


def _is_qname(tag: str, namespaces: frozenset[str], *names: str) -> bool:
    return _namespace(tag) in namespaces and _local_name(tag) in names


def _relationship_attribute(node: ET.Element, *names: str) -> str | None:
    for attribute, value in node.attrib.items():
        if _is_qname(attribute, _OFFICE_REL_NAMESPACES, *names):
            return value
    return None


def _rels_part(source_part: str) -> str:
    directory, filename = posixpath.split(source_part)
    return posixpath.join(directory, "_rels", f"{filename}.rels")


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
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source_part), decoded))
    if resolved in ("", ".", "..") or resolved.startswith("../"):
        return None
    return resolved


def _read_xml(
    package: zipfile.ZipFile,
    part: str,
    gaps: list[str],
    context: str,
) -> ET.Element | None:
    try:
        return ET.fromstring(package.read(part))
    except KeyError:
        gaps.append(f"{context}: OOXML 部品 {part} が見つかりません")
    except ET.ParseError as exc:
        gaps.append(f"{context}: OOXML 部品 {part} の XML が不正 ({exc})")
    return None


def _load_relationships(
    package: zipfile.ZipFile,
    source_part: str,
    gaps: list[str],
    context: str,
    *,
    required: bool = False,
) -> dict[str, _Relationship]:
    rels_name = _rels_part(source_part)
    if rels_name not in package.namelist():
        if required:
            gaps.append(f"{context}: relationships 部品 {rels_name} が見つかりません")
        return {}
    root = _read_xml(package, rels_name, gaps, context)
    if root is None:
        return {}
    if not _is_qname(root.tag, _PACKAGE_REL_NAMESPACES, "Relationships"):
        gaps.append(f"{context}: relationships の名前空間は未対応です")
        return {}
    relationships: dict[str, _Relationship] = {}
    duplicate_ids: set[str] = set()
    for node in root:
        if not _is_qname(node.tag, _PACKAGE_REL_NAMESPACES, "Relationship"):
            if _local_name(node.tag) == "Relationship":
                gaps.append(f"{context}: relationship の名前空間は未対応です")
            continue
        rel_id = node.get("Id")
        rel_type = node.get("Type")
        target = node.get("Target")
        if not rel_id or not rel_type or not target:
            gaps.append(f"{context}: 不正な relationship を検出しました")
            continue
        if rel_id in relationships or rel_id in duplicate_ids:
            relationships.pop(rel_id, None)
            duplicate_ids.add(rel_id)
            gaps.append(f"{context}: relationship ID {rel_id} が重複しています")
            continue
        relationships[rel_id] = _Relationship(
            id=rel_id,
            type=rel_type,
            target=target,
            external=node.get("TargetMode", "").lower() == "external",
        )
    return relationships


def _relationship_part(
    package_parts: set[str],
    source_part: str,
    relationship: _Relationship | None,
    gaps: list[str],
    context: str,
    rel_id: str | None,
    expected_type: str,
) -> str | None:
    label = rel_id or "(r:id なし)"
    if relationship is None:
        gaps.append(f"{context}: relationship {label} は未解決です")
        return None
    if relationship.external:
        gaps.append(f"{context}: relationship {label} は外部 Target のため未対応です")
        return None
    if relationship.type not in _RELATIONSHIP_TYPES[expected_type]:
        gaps.append(
            f"{context}: relationship {label} の型 {relationship.type} は未対応です"
        )
        return None
    part = _resolve_target(source_part, relationship.target)
    if part is None:
        gaps.append(f"{context}: relationship {label} の Target は不正または範囲外です")
        return None
    if part not in package_parts:
        gaps.append(f"{context}: relationship {label} の参照先 {part} が見つかりません")
        return None
    return part


def _drawing_artifacts(
    package: zipfile.ZipFile,
    package_parts: set[str],
    sheet_name: str,
    drawing_part: str,
    gaps: list[str],
) -> tuple[dict[ArtifactType, int], dict[ArtifactType, set[str]]]:
    counts: dict[ArtifactType, int] = {artifact_type: 0 for artifact_type in _TYPE_ORDER}
    parts: dict[ArtifactType, set[str]] = {
        artifact_type: set() for artifact_type in _TYPE_ORDER
    }
    root = _read_xml(package, drawing_part, gaps, sheet_name)
    if root is None:
        return counts, parts
    if not _is_qname(root.tag, _XDR_NAMESPACES, "wsDr"):
        gaps.append(f"{sheet_name}: drawing {drawing_part} の名前空間は未対応です")
        return counts, parts
    relationships = _load_relationships(package, drawing_part, gaps, sheet_name)
    if any(
        _is_qname(node.tag, _MC_NAMESPACES, "AlternateContent")
        for node in root.iter()
    ):
        gaps.append(f"{sheet_name}: drawing {drawing_part} の AlternateContent は未対応です")
    elif any(_local_name(node.tag) == "AlternateContent" for node in root.iter()):
        gaps.append(
            f"{sheet_name}: drawing {drawing_part} の AlternateContent 名前空間は未対応です"
        )

    for anchor in root:
        anchor_name = _local_name(anchor.tag)
        if not _is_qname(
            anchor.tag,
            _XDR_NAMESPACES,
            "twoCellAnchor",
            "oneCellAnchor",
            "absoluteAnchor",
        ):
            if anchor_name in ("twoCellAnchor", "oneCellAnchor", "absoluteAnchor"):
                gaps.append(
                    f"{sheet_name}: drawing {drawing_part} の名前空間は未対応です"
                )
            continue
        for node in anchor:
            kind = _local_name(node.tag)
            if _is_qname(node.tag, _XDR_NAMESPACES, "sp", "cxnSp", "grpSp"):
                counts["shape"] += 1
                parts["shape"].add(drawing_part)
            elif _is_qname(node.tag, _XDR_NAMESPACES, "pic"):
                counts["image"] += 1
                blip = next(
                    (
                        item
                        for item in node.iter()
                        if _is_qname(item.tag, _DML_NAMESPACES, "blip")
                    ),
                    None,
                )
                rel_id = (
                    None
                    if blip is None
                    else _relationship_attribute(blip, "embed", "link")
                )
                image_part = _relationship_part(
                    package_parts,
                    drawing_part,
                    relationships.get(rel_id) if rel_id else None,
                    gaps,
                    sheet_name,
                    rel_id,
                    "image",
                )
                if image_part:
                    parts["image"].add(image_part)
            elif _is_qname(node.tag, _XDR_NAMESPACES, "graphicFrame"):
                charts = [
                    item
                    for item in node.iter()
                    if _is_qname(item.tag, _CHART_NAMESPACES, "chart")
                ]
                if not charts:
                    gaps.append(f"{sheet_name}: drawing {drawing_part} の unknown graphic frame は未対応です")
                for chart in charts:
                    counts["chart"] += 1
                    rel_id = _relationship_attribute(chart, "id")
                    chart_part = _relationship_part(
                        package_parts,
                        drawing_part,
                        relationships.get(rel_id) if rel_id else None,
                        gaps,
                        sheet_name,
                        rel_id,
                        "chart",
                    )
                    if chart_part:
                        parts["chart"].add(chart_part)
            elif kind in ("sp", "cxnSp", "grpSp", "pic", "graphicFrame"):
                gaps.append(
                    f"{sheet_name}: drawing {drawing_part} の {kind} 名前空間は未対応です"
                )
    return counts, parts


def _sheet_artifacts(
    package: zipfile.ZipFile,
    package_parts: set[str],
    sheet_name: str,
    sheet_part: str,
    gaps: list[str],
) -> list[ir.SheetArtifact]:
    counts: dict[ArtifactType, int] = {artifact_type: 0 for artifact_type in _TYPE_ORDER}
    parts: dict[ArtifactType, set[str]] = {
        artifact_type: set() for artifact_type in _TYPE_ORDER
    }
    root = _read_xml(package, sheet_part, gaps, sheet_name)
    if root is None:
        return []
    if not _is_qname(root.tag, _SSML_NAMESPACES, "worksheet"):
        gaps.append(f"{sheet_name}: worksheet の名前空間は未対応です")
        return []
    relationships = _load_relationships(package, sheet_part, gaps, sheet_name)

    for node in root.iter():
        kind = _local_name(node.tag)
        if kind in ("legacyDrawing", "legacyDrawingHF"):
            if _is_qname(
                node.tag,
                _SSML_NAMESPACES,
                "legacyDrawing",
                "legacyDrawingHF",
            ):
                gaps.append(f"{sheet_name}: VML drawing は未対応です")
            else:
                gaps.append(f"{sheet_name}: VML drawing の名前空間は未対応です")
            continue
        if kind not in ("drawing", "pivotTablePart"):
            continue
        if not _is_qname(node.tag, _SSML_NAMESPACES, "drawing", "pivotTablePart"):
            gaps.append(f"{sheet_name}: {kind} の名前空間は未対応です")
            continue
        rel_id = _relationship_attribute(node, "id")
        relationship = relationships.get(rel_id) if rel_id else None
        expected_type = "drawing" if kind == "drawing" else "pivotTable"
        target = _relationship_part(
            package_parts,
            sheet_part,
            relationship,
            gaps,
            sheet_name,
            rel_id,
            expected_type,
        )
        if target is None:
            continue
        if kind == "pivotTablePart":
            counts["pivot"] += 1
            parts["pivot"].add(target)
            continue
        drawing_counts, drawing_parts = _drawing_artifacts(
            package, package_parts, sheet_name, target, gaps
        )
        for artifact_type in _TYPE_ORDER:
            counts[artifact_type] += drawing_counts[artifact_type]
            parts[artifact_type].update(drawing_parts[artifact_type])

    artifacts = [
        ir.SheetArtifact(
            type=artifact_type,
            count=counts[artifact_type],
            ooxml_parts=sorted(parts[artifact_type]),
        )
        for artifact_type in _TYPE_ORDER
        if counts[artifact_type]
    ]
    for artifact in artifacts:
        gaps.append(f"{sheet_name}: {artifact.type} の詳細抽出は未対応です")
    return artifacts


def extract_sheet_artifacts(path: Path) -> tuple[dict[str, list[ir.SheetArtifact]], list[str]]:
    gaps: list[str] = []
    extracted: dict[str, list[ir.SheetArtifact]] = {}
    with zipfile.ZipFile(path) as package:
        package_parts = set(package.namelist())
        workbook_part = "xl/workbook.xml"
        workbook = _read_xml(package, workbook_part, gaps, "workbook")
        if workbook is None:
            return extracted, gaps
        if not _is_qname(workbook.tag, _SSML_NAMESPACES, "workbook"):
            gaps.append("workbook: workbook の名前空間は未対応です")
            return extracted, gaps
        relationships = _load_relationships(
            package, workbook_part, gaps, "workbook", required=True
        )
        for sheet in workbook.iter():
            if not _is_qname(sheet.tag, _SSML_NAMESPACES, "sheet"):
                continue
            name = sheet.get("name")
            rel_id = _relationship_attribute(sheet, "id")
            if not name:
                gaps.append("workbook: 名前のない sheet を検出しました")
                continue
            relationship = relationships.get(rel_id) if rel_id else None
            if relationship and relationship.type in _RELATIONSHIP_TYPES["chartsheet"]:
                gaps.append(f"{name}: chartsheet の artifact 抽出は未対応です")
                continue
            sheet_part = _relationship_part(
                package_parts,
                workbook_part,
                relationship,
                gaps,
                name,
                rel_id,
                "worksheet",
            )
            if sheet_part:
                extracted[name] = _sheet_artifacts(
                    package, package_parts, name, sheet_part, gaps
                )
    return extracted, gaps
