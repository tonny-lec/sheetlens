import re
from pathlib import Path
from typing import Literal

import yaml
from openpyxl.utils import range_boundaries
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from sheetlens.model import ir


class AnnotationError(Exception):
    pass


class AnnotationTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    range: str | None = None
    kind: Literal[
        "input_source", "dropdown_semantics", "trigger_timing",
        "alert_action", "sheet_role", "free_note", "hidden_reason",
    ]
    value: str | None = None
    by: str | None = None
    when: str | None = None
    values: dict[str, str] = Field(default_factory=dict)
    note: str | None = None


class SheetAnnotations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sheet: str
    role: str | None = None
    workflow_stage: str | None = None
    targets: list[AnnotationTarget] = Field(default_factory=list)
    questions_answered: list[str] = Field(default_factory=list)


def split_ranges(value: str) -> list[str]:
    """注釈の range 文字列をカンマ/空白区切りで個別範囲に分割する。"""
    return [p for p in re.split(r"[\s,]+", value.strip()) if p]


def load_annotations(dir_path: Path) -> list[SheetAnnotations]:
    out: list[SheetAnnotations] = []
    for path in sorted(dir_path.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            out.append(SheetAnnotations.model_validate(data))
        except (yaml.YAMLError, ValidationError) as e:
            raise AnnotationError(f"{path.name}: {e}") from e
    return out


def find_orphans(wb: ir.Workbook, anns: list[SheetAnnotations]) -> list[str]:
    sheets = {s.name: s for s in wb.sheets}
    orphans: list[str] = []
    for ann in anns:
        sheet = sheets.get(ann.sheet)
        if sheet is None:
            orphans.append(f"{ann.sheet}: 注釈対象のシートが存在しません")
            continue
        for t in ann.targets:
            if not t.range:
                continue
            if t.kind in ("trigger_timing", "hidden_reason"):
                continue
            if not sheet.used_range:
                orphans.append(f"{ann.sheet}!{t.range}: シートが空です")
                continue
            u_min_c, u_min_r, u_max_c, u_max_r = range_boundaries(sheet.used_range)
            for part in split_ranges(t.range):
                try:
                    min_c, min_r, max_c, max_r = range_boundaries(part)
                except ValueError:
                    orphans.append(f"{ann.sheet}!{part}: range 指定が不正です")
                    continue
                if None in (min_c, min_r, max_c, max_r):
                    orphans.append(f"{ann.sheet}!{part}: range 指定が不正です")
                    continue
                if not (
                    u_min_c <= min_c
                    and u_min_r <= min_r
                    and max_c <= u_max_c
                    and max_r <= u_max_r
                ):
                    orphans.append(
                        f"{ann.sheet}!{part}: 現在の使用範囲 {sheet.used_range} の外にあります"
                    )
    return orphans
