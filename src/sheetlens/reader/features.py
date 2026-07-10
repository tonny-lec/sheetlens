from dataclasses import dataclass

from openpyxl.utils.cell import SHEETRANGE_RE, range_boundaries
from openpyxl.xml.constants import MAX_COLUMN, MAX_ROW

from sheetlens.model import ir


@dataclass(frozen=True)
class _RangeTarget:
    sheet: str
    min_col: int
    min_row: int
    max_col: int
    max_row: int


@dataclass(frozen=True)
class _ListResolution:
    choices: list[str]
    reason: str | None = None


def _formula_source(formula: str) -> str:
    source = formula.strip()
    if source.startswith("="):
        source = source[1:].strip()
    return source


def _unsupported_function_reason(source: str) -> str | None:
    upper = source.lstrip().upper()
    if upper.startswith("INDIRECT("):
        return "unsupported_indirect"
    if upper.startswith("OFFSET("):
        return "unsupported_offset"
    return None


def _is_defined_name_candidate(source: str) -> bool:
    if not source or not (source[0].isalpha() or source[0] in "_\\"):
        return False
    return all(char.isalnum() or char in "._\\" for char in source[1:])


def _format_validation_gap(
    sheet: str,
    ranges: list[str],
    formula1: str,
    reason: str,
) -> str:
    sorted_ranges = ", ".join(sorted(ranges))
    return (
        f"{sheet}: 入力規則 {sorted_ranges} の選択肢を解決できません "
        f"(formula1={formula1!r}; reason={reason})"
    )


def _parse_static_range(source: str, default_sheet: str | None) -> _RangeTarget | None:
    try:
        if "!" in source:
            match = SHEETRANGE_RE.fullmatch(source)
            if match is None:
                return None
            sheet = match.group("quoted") or match.group("notquoted")
            sheet = sheet.replace("''", "'")
            bounds = range_boundaries(match.group("cells"))
        else:
            if default_sheet is None:
                return None
            sheet = default_sheet
            bounds = range_boundaries(source)
    except (AttributeError, TypeError, ValueError):
        return None

    if any(value is None for value in bounds):
        return None
    min_col, min_row, max_col, max_row = bounds
    if not (
        1 <= min_col <= max_col <= MAX_COLUMN
        and 1 <= min_row <= max_row <= MAX_ROW
    ):
        return None
    return _RangeTarget(sheet, min_col, min_row, max_col, max_row)


def _read_range(wb_v, target: _RangeTarget) -> _ListResolution:
    if any(marker in target.sheet for marker in (":", "[", "]")):
        return _ListResolution([], "unsupported_reference")
    if target.sheet not in wb_v.sheetnames:
        return _ListResolution([], "sheet_not_found")
    ws = wb_v[target.sheet]
    choices = [
        str(cell.value)
        for row in ws.iter_rows(
            min_col=target.min_col,
            min_row=target.min_row,
            max_col=target.max_col,
            max_row=target.max_row,
        )
        for cell in row
        if cell.value is not None
    ]
    return _ListResolution(choices)


def _find_defined_name(mapping, name: str):
    matches = [
        definition
        for key, definition in mapping.items()
        if key.casefold() == name.casefold()
    ]
    if len(matches) > 1:
        return None, "ambiguous_name"
    return (matches[0], None) if matches else (None, None)


def _resolve_definition(wb_v, definition, *, default_sheet: str | None) -> _ListResolution:
    source = _formula_source(definition.attr_text or "")
    function_reason = _unsupported_function_reason(source)
    if function_reason is not None:
        return _ListResolution([], function_reason)
    target = _parse_static_range(source, default_sheet)
    if target is not None:
        return _read_range(wb_v, target)
    if "," in source:
        return _ListResolution([], "unsupported_reference")
    reason = (
        "invalid_range"
        if "!" in source or "#REF!" in source
        else "unsupported_reference"
    )
    return _ListResolution([], reason)


def _resolve_list(wb_v, current_sheet: str, formula: str) -> _ListResolution:
    source = _formula_source(formula)
    if source.startswith("="):
        return _ListResolution([], "unsupported_reference")

    target = _parse_static_range(source, current_sheet)
    if target is not None:
        return _read_range(wb_v, target)

    function_reason = _unsupported_function_reason(source)
    if function_reason is not None:
        return _ListResolution([], function_reason)
    if "," in source:
        return _ListResolution([], "unsupported_reference")
    if "!" in source or "#REF!" in source:
        return _ListResolution([], "invalid_range")
    if not _is_defined_name_candidate(source):
        return _ListResolution([], "unsupported_reference")

    if current_sheet not in wb_v.sheetnames:
        return _ListResolution([], "sheet_not_found")

    local_definition, reason = _find_defined_name(
        wb_v[current_sheet].defined_names,
        source,
    )
    if reason is not None:
        return _ListResolution([], reason)
    if local_definition is not None:
        return _resolve_definition(
            wb_v,
            local_definition,
            default_sheet=current_sheet,
        )

    workbook_definition, reason = _find_defined_name(wb_v.defined_names, source)
    if reason is not None:
        return _ListResolution([], reason)
    if workbook_definition is None:
        return _ListResolution([], "name_not_found")
    return _resolve_definition(wb_v, workbook_definition, default_sheet=None)


def read_validations(
    ws_f,
    wb_v,
    *,
    extraction_gaps: list[str] | None = None,
) -> list[ir.ValidationRule]:
    gap_sink = [] if extraction_gaps is None else extraction_gaps
    rules: list[ir.ValidationRule] = []
    for dv in ws_f.data_validations.dataValidation:
        f1 = dv.formula1
        ranges = [str(r) for r in dv.sqref.ranges]
        choices: list[str] = []
        if dv.type == "list" and f1:
            if f1.startswith('"'):
                choices = [s.strip() for s in f1.strip('"').split(",")]
            else:
                resolution = _resolve_list(wb_v, ws_f.title, f1)
                choices = resolution.choices
                if resolution.reason is not None:
                    gap_sink.append(
                        _format_validation_gap(
                            ws_f.title,
                            ranges,
                            f1,
                            resolution.reason,
                        )
                    )
        rules.append(
            ir.ValidationRule(
                ranges=ranges,
                type=dv.type or "unknown",
                formula1=f1,
                choices=choices,
            )
        )
    return rules


def read_conditional_formats(ws_f) -> list[ir.ConditionalFormat]:
    out: list[ir.ConditionalFormat] = []
    for fmt in ws_f.conditional_formatting:
        for rule in fmt.rules:
            formulas = list(getattr(rule, "formula", None) or [])
            out.append(
                ir.ConditionalFormat(
                    range=str(fmt.sqref),
                    rule_type=rule.type or "unknown",
                    operator=getattr(rule, "operator", None),
                    formula=formulas[0] if formulas else None,
                    stop_if_true=bool(rule.stopIfTrue),
                )
            )
    return out
