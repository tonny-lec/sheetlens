from sheetlens.model import ir


def _resolve_list(wb_v, current_sheet: str, formula: str) -> list[str]:
    """'=区分マスタ!$A$2:$A$3' 形式のリスト参照を実際の選択肢値に展開する。"""
    ref = formula.lstrip("=")
    if "!" in ref:
        sheet_part, ref = ref.rsplit("!", 1)
        sheet_part = sheet_part.strip("'")
    else:
        sheet_part = current_sheet
    try:
        ws = wb_v[sheet_part]
        found = ws[ref.replace("$", "")]
        rows = found if isinstance(found, tuple) else ((found,),)
        values: list[str] = []
        for row in rows:
            for c in row if isinstance(row, tuple) else (row,):
                if c.value is not None:
                    values.append(str(c.value))
        return values
    except (KeyError, ValueError):
        return []


def read_validations(ws_f, wb_v) -> list[ir.ValidationRule]:
    rules: list[ir.ValidationRule] = []
    for dv in ws_f.data_validations.dataValidation:
        f1 = dv.formula1
        choices: list[str] = []
        if dv.type == "list" and f1:
            if f1.startswith('"'):
                choices = [s.strip() for s in f1.strip('"').split(",")]
            else:
                choices = _resolve_list(wb_v, ws_f.title, f1)
        rules.append(
            ir.ValidationRule(
                ranges=[str(r) for r in dv.sqref.ranges],
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
