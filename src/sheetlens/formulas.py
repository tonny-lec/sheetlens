from __future__ import annotations

import re
from collections.abc import Iterable

from openpyxl.formula import Tokenizer
from openpyxl.formula.tokenizer import Token, TokenizerError
from openpyxl.formula.translate import Translator
from openpyxl.utils.cell import (
    column_index_from_string,
    coordinate_to_tuple,
    range_boundaries,
)

from sheetlens.model import ir

_CELL_RE = re.compile(r"(\$?)([A-Za-z]{1,3})(\$?)([1-9][0-9]{0,6})\Z")
_COL_RE = re.compile(r"(\$?)([A-Za-z]{1,3})\Z")
_ROW_RE = re.compile(r"(\$?)([1-9][0-9]{0,6})\Z")
_EXTERNAL_BOOK_RE = re.compile(r"\[([^\]]+)\]")
_EXTERNAL_FILE_RE = re.compile(r".+\.xls[xmb]?\Z", re.IGNORECASE)


def _tokens(formula: str) -> list[Token]:
    source = formula if formula.startswith("=") else f"={formula}"
    return Tokenizer(source).items


def _normalize_endpoint(reference: str, origin_row: int, origin_col: int) -> str | None:
    match = _CELL_RE.fullmatch(reference)
    if match:
        col_index = column_index_from_string(match.group(2).upper())
        row = int(match.group(4))
        row_part = f"R{row}" if match.group(3) else f"R[{row - origin_row}]"
        col_part = (
            f"C{col_index}"
            if match.group(1)
            else f"C[{col_index - origin_col}]"
        )
        return f"{row_part}{col_part}"
    match = _COL_RE.fullmatch(reference)
    if match:
        col_index = column_index_from_string(match.group(2).upper())
        return f"C{col_index}" if match.group(1) else f"C[{col_index - origin_col}]"
    match = _ROW_RE.fullmatch(reference)
    if match:
        row = int(match.group(2))
        return f"R{row}" if match.group(1) else f"R[{row - origin_row}]"
    return None


def _normalize_range(reference: str, origin_row: int, origin_col: int) -> str:
    worksheet, range_part = Translator.strip_ws_name(reference)
    normalized = [
        _normalize_endpoint(part, origin_row, origin_col)
        for part in range_part.split(":")
    ]
    if any(part is None for part in normalized):
        return reference
    return worksheet + ":".join(part for part in normalized if part is not None)


def normalize_formula(formula: str, *, origin: str) -> str:
    row, col = coordinate_to_tuple(origin)
    try:
        tokens = _tokens(formula)
    except (TokenizerError, ValueError):
        return formula
    return "=" + "".join(
        _normalize_range(token.value, row, col)
        if token.type == Token.OPERAND and token.subtype == Token.RANGE
        else token.value
        for token in tokens
    )


def _quote_sheet(name: str) -> str:
    return f"'{name.replace(chr(39), chr(39) * 2)}'"


def _source(kind: str, sheet: str, reference: str) -> str:
    return f"{kind}:{_quote_sheet(sheet)}!{reference.upper()}"


def _split_qualifier(reference: str) -> tuple[str | None, str | None, str]:
    worksheet, range_part = Translator.strip_ws_name(reference)
    if not worksheet:
        match = _EXTERNAL_BOOK_RE.match(range_part)
        if match is None or not (
            match.group(1).isdigit() or _EXTERNAL_FILE_RE.fullmatch(match.group(1))
        ):
            return None, None, range_part
        return match.group(1), None, range_part[match.end() :]
    qualifier = worksheet[:-1]
    if qualifier.startswith("'") and qualifier.endswith("'"):
        qualifier = qualifier[1:-1].replace("''", "'")
    match = _EXTERNAL_BOOK_RE.search(qualifier)
    if match is None:
        return None, qualifier or None, range_part
    return match.group(1), qualifier[match.end() :] or None, range_part


def _a1_range(reference: str) -> str | None:
    normalized: list[str] = []
    for part in reference.split(":"):
        match = _CELL_RE.fullmatch(part)
        if match:
            normalized.append(
                f"{match.group(1)}{match.group(2).upper()}"
                f"{match.group(3)}{match.group(4)}"
            )
            continue
        match = _COL_RE.fullmatch(part)
        if match:
            normalized.append(f"{match.group(1)}{match.group(2).upper()}")
            continue
        match = _ROW_RE.fullmatch(part)
        if match:
            normalized.append(f"{match.group(1)}{match.group(2)}")
            continue
        return None
    return ":".join(normalized)


def _has_relative_axis(reference: str) -> bool:
    for part in reference.split(":"):
        match = _CELL_RE.fullmatch(part)
        if match and (not match.group(1) or not match.group(3)):
            return True
        match = _COL_RE.fullmatch(part)
        if match and not match.group(1):
            return True
        match = _ROW_RE.fullmatch(part)
        if match and not match.group(1):
            return True
    return False


def _unresolved(
    source: str,
    raw_reference: str,
    *,
    target_workbook: str | None = None,
    target_sheet: str | None = None,
) -> ir.DependencyEdge:
    return ir.DependencyEdge(
        source=source,
        target_workbook=target_workbook,
        target_sheet=target_sheet,
        target_range=raw_reference,
        unresolved=True,
    )


class _DependencyParser:
    def __init__(self, workbook: ir.Workbook):
        self.sheets = {sheet.name.casefold(): sheet.name for sheet in workbook.sheets}
        names: dict[str, list[tuple[str, str]]] = {}
        for name, definition in workbook.defined_names.items():
            names.setdefault(name.casefold(), []).append((name, definition))
        self.names = names

    def formula_edges(
        self,
        formula: str,
        *,
        source: str,
        source_sheet: str,
        name_stack: tuple[str, ...] = (),
        root_name: str | None = None,
        defined_context: bool = False,
        multi_cell_source: bool = False,
    ) -> list[ir.DependencyEdge]:
        try:
            tokens = _tokens(formula)
        except (TokenizerError, ValueError):
            return [_unresolved(source, root_name or formula)]
        if defined_context and any(token.type == Token.FUNC for token in tokens):
            return [_unresolved(source, root_name or formula)]
        edges: list[ir.DependencyEdge] = []
        for token in tokens:
            if token.type != Token.OPERAND or token.subtype != Token.RANGE:
                continue
            edges.extend(
                self.reference_edges(
                    token.value,
                    source=source,
                    source_sheet=source_sheet,
                    name_stack=name_stack,
                    root_name=root_name,
                    defined_context=defined_context,
                    multi_cell_source=multi_cell_source,
                )
            )
        if defined_context and not edges:
            return [_unresolved(source, root_name or formula)]
        return edges

    def reference_edges(
        self,
        reference: str,
        *,
        source: str,
        source_sheet: str,
        name_stack: tuple[str, ...],
        root_name: str | None,
        defined_context: bool,
        multi_cell_source: bool,
    ) -> list[ir.DependencyEdge]:
        workbook, target_sheet, range_part = _split_qualifier(reference)
        target_range = _a1_range(range_part)
        if target_sheet and ":" in target_sheet:
            return [
                _unresolved(
                    source,
                    root_name or reference,
                    target_workbook=workbook,
                )
            ]
        if target_range is not None:
            if defined_context and target_sheet is None:
                return [_unresolved(source, root_name or reference)]
            requested_sheet = target_sheet or source_sheet
            canonical_sheet = self.sheets.get(requested_sheet.casefold())
            if multi_cell_source and _has_relative_axis(range_part):
                return [
                    _unresolved(
                        source,
                        target_range,
                        target_workbook=workbook,
                        target_sheet=(
                            target_sheet
                            if workbook is not None
                            else canonical_sheet or requested_sheet
                        ),
                    )
                ]
            if workbook is not None:
                return [
                    ir.DependencyEdge(
                        source=source,
                        target_workbook=workbook,
                        target_sheet=target_sheet,
                        target_range=target_range,
                        unresolved=True,
                    )
                ]
            return [
                ir.DependencyEdge(
                    source=source,
                    target_sheet=canonical_sheet or requested_sheet,
                    target_range=target_range,
                    unresolved=canonical_sheet is None,
                )
            ]
        if target_sheet is not None or workbook is not None:
            return [
                _unresolved(
                    source,
                    root_name or range_part or reference,
                    target_workbook=workbook,
                    target_sheet=target_sheet,
                )
            ]

        key = reference.casefold()
        definitions = self.names.get(key, [])
        if len(definitions) != 1 or key in name_stack:
            return [_unresolved(source, root_name or reference)]
        _, definition = definitions[0]
        return self.formula_edges(
            definition,
            source=source,
            source_sheet=source_sheet,
            name_stack=(*name_stack, key),
            root_name=root_name or reference,
            defined_context=True,
            multi_cell_source=multi_cell_source,
        )


def _range_parts(reference: str) -> list[str]:
    return [part for part in re.split(r"[\s,]+", reference.strip()) if part]


def _is_multi_cell(reference: str) -> bool:
    try:
        min_col, min_row, max_col, max_row = range_boundaries(reference)
    except (TypeError, ValueError):
        return True
    return min_col != max_col or min_row != max_row


def _deduplicate(edges: Iterable[ir.DependencyEdge]) -> list[ir.DependencyEdge]:
    by_key = {
        (
            edge.source,
            edge.target_workbook,
            edge.target_sheet,
            edge.target_range,
            edge.unresolved,
        ): edge
        for edge in edges
    }
    return [
        by_key[key]
        for key in sorted(
            by_key,
            key=lambda value: (
                value[0],
                value[4],
                value[1] or "",
                value[2] or "",
                value[3] or "",
            ),
        )
    ]


def dependency_edges(workbook: ir.Workbook) -> list[ir.DependencyEdge]:
    parser = _DependencyParser(workbook)
    edges: list[ir.DependencyEdge] = []
    for sheet in workbook.sheets:
        for cell in sheet.cells:
            if cell.formula:
                edges.extend(
                    parser.formula_edges(
                        cell.formula,
                        source=_source("cell", sheet.name, cell.ref),
                        source_sheet=sheet.name,
                    )
                )
        for validation in sheet.validations:
            if not validation.formula1:
                continue
            for reference in validation.ranges:
                edges.extend(
                    parser.formula_edges(
                        validation.formula1,
                        source=_source("validation", sheet.name, reference),
                        source_sheet=sheet.name,
                        multi_cell_source=_is_multi_cell(reference),
                    )
                )
        for conditional_format in sheet.conditional_formats:
            for reference in _range_parts(conditional_format.range):
                for formula in conditional_format.formulas:
                    edges.extend(
                        parser.formula_edges(
                            formula,
                            source=_source(
                                "conditional_format", sheet.name, reference
                            ),
                            source_sheet=sheet.name,
                            multi_cell_source=_is_multi_cell(reference),
                        )
                    )
    return _deduplicate(edges)
