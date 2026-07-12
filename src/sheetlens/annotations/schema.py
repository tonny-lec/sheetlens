import re
from pathlib import Path
from typing import Annotated, Literal, TypeAlias

import yaml
from openpyxl.utils import range_boundaries
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator

from sheetlens.model import ir


class AnnotationError(Exception):
    pass


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class _AnnotationTargetBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InputSourceTarget(_AnnotationTargetBase):
    kind: Literal["input_source"]
    range: NonEmptyString
    value: NonEmptyString
    by: NonEmptyString | None = None
    when: NonEmptyString | None = None
    note: NonEmptyString | None = None


class DropdownSemanticsTarget(_AnnotationTargetBase):
    kind: Literal["dropdown_semantics"]
    range: NonEmptyString
    values: dict[NonEmptyString, NonEmptyString]
    note: NonEmptyString | None = None

    @model_validator(mode="after")
    def require_values(self) -> "DropdownSemanticsTarget":
        if not self.values:
            raise ValueError("dropdown_semantics target requires at least one value")
        return self


class TriggerTimingTarget(_AnnotationTargetBase):
    kind: Literal["trigger_timing"]
    range: NonEmptyString
    when: NonEmptyString
    note: NonEmptyString | None = None


class AlertActionTarget(_AnnotationTargetBase):
    kind: Literal["alert_action"]
    range: NonEmptyString
    note: NonEmptyString


class SheetRoleTarget(_AnnotationTargetBase):
    kind: Literal["sheet_role"]
    value: NonEmptyString | None = None
    note: NonEmptyString | None = None

    @model_validator(mode="after")
    def require_content(self) -> "SheetRoleTarget":
        if self.value is None and self.note is None:
            raise ValueError("sheet_role target requires value or note")
        return self


class FreeNoteTarget(_AnnotationTargetBase):
    kind: Literal["free_note"]
    range: NonEmptyString | None = None
    note: NonEmptyString


class HiddenReasonTarget(_AnnotationTargetBase):
    kind: Literal["hidden_reason"]
    range: NonEmptyString | None = None
    value: NonEmptyString | None = None
    note: NonEmptyString | None = None

    @model_validator(mode="after")
    def require_content(self) -> "HiddenReasonTarget":
        if self.value is None and self.note is None:
            raise ValueError("hidden_reason target requires value or note")
        return self


AnnotationTarget: TypeAlias = Annotated[
    InputSourceTarget
    | DropdownSemanticsTarget
    | TriggerTimingTarget
    | AlertActionTarget
    | SheetRoleTarget
    | FreeNoteTarget
    | HiddenReasonTarget,
    Field(discriminator="kind"),
]


class SheetAnnotations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sheet: NonEmptyString
    role: NonEmptyString | None = None
    workflow_stage: NonEmptyString | None = None
    targets: list[AnnotationTarget] = Field(default_factory=list)
    questions_answered: list[NonEmptyString] = Field(default_factory=list)


def split_ranges(value: str) -> list[str]:
    """注釈の range 文字列をカンマ/空白区切りで個別範囲に分割する。"""
    return [p for p in re.split(r"[\s,]+", value.strip()) if p]


def load_annotations(dir_path: Path) -> list[SheetAnnotations]:
    out: list[SheetAnnotations] = []
    by_sheet: dict[str, Path] = {}
    for path in sorted(dir_path.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            annotation = SheetAnnotations.model_validate(data)
            previous = by_sheet.get(annotation.sheet)
            if previous is not None:
                raise AnnotationError(
                    f"{path.name}: sheet {annotation.sheet!r} は {previous.name} で既に定義されています。"
                    "同一シートの注釈は1ファイルにまとめてください。"
                )
            by_sheet[annotation.sheet] = path
            out.append(annotation)
        except AnnotationError:
            raise
        except (yaml.YAMLError, ValidationError) as e:
            raise AnnotationError(f"{path.name}: {e}") from e
    return out


def find_orphans(wb: ir.Workbook, anns: list[SheetAnnotations]) -> list[str]:
    sheets = {s.name: s for s in wb.sheets}
    orphans: list[str] = []
    for ann in anns:
        sheet = sheets.get(ann.sheet)
        if sheet is None:
            if ann.sheet == "(VBA)" and all(t.kind == "trigger_timing" for t in ann.targets):
                continue
            orphans.append(f"{ann.sheet}: 注釈対象のシートが存在しません")
            continue
        for t in ann.targets:
            target_range = getattr(t, "range", None)
            if not target_range:
                continue
            if t.kind in ("trigger_timing", "hidden_reason"):
                continue
            available_range = (
                sheet.structural_range or sheet.used_range or sheet.content_range
            )
            if not available_range:
                orphans.append(f"{ann.sheet}!{target_range}: シートが空です")
                continue
            u_min_c, u_min_r, u_max_c, u_max_r = range_boundaries(available_range)
            for part in split_ranges(target_range):
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
                        f"{ann.sheet}!{part}: 現在の構造範囲 {available_range} の外にあります"
                    )
    return orphans
