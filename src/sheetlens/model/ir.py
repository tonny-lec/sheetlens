from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Primitive = str | int | float | bool | None
CellValueType = Literal[
    "string",
    "number",
    "boolean",
    "date",
    "time",
    "datetime",
    "duration",
    "error",
]
CellDisplaySemantics = Literal[
    "percentage",
    "currency",
    "date",
    "time",
    "datetime",
    "duration",
    "leading_zero",
    "error",
]


class Cell(BaseModel):
    ref: str
    value: Primitive = None
    formula: str | None = None
    value_type: CellValueType | None = None
    number_format: str | None = None
    display_semantics: CellDisplaySemantics | None = None


class ValidationRule(BaseModel):
    ranges: list[str]
    type: str
    formula1: str | None = None
    choices: list[str] = Field(default_factory=list)


class ConditionalValue(BaseModel):
    type: str | None = None
    value: str | float | int | None = None
    gte: bool | None = None


class ConditionalColor(BaseModel):
    type: str
    value: str | float | int | bool
    tint: float = 0.0


class ConditionalColorScale(BaseModel):
    conditions: list[ConditionalValue] = Field(default_factory=list)
    colors: list[ConditionalColor] = Field(default_factory=list)


class ConditionalDataBar(BaseModel):
    conditions: list[ConditionalValue] = Field(default_factory=list)
    color: ConditionalColor
    show_value: bool | None = None
    min_length: int | None = None
    max_length: int | None = None


class ConditionalIconSet(BaseModel):
    icon_style: str | None = None
    conditions: list[ConditionalValue] = Field(default_factory=list)
    show_value: bool | None = None
    percent: bool | None = None
    reverse: bool | None = None


class OoxmlNode(BaseModel):
    tag: str
    attributes: dict[str, str] = Field(default_factory=dict)
    text: str | None = None
    children: list[OoxmlNode] = Field(default_factory=list)


class ConditionalFormat(BaseModel):
    range: str
    rule_type: str
    operator: str | None = None
    formulas: list[str] = Field(default_factory=list)
    stop_if_true: bool = False
    color_scale: ConditionalColorScale | None = None
    data_bar: ConditionalDataBar | None = None
    icon_set: ConditionalIconSet | None = None
    dxf: OoxmlNode | None = None

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_formula(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        migrated = dict(data)
        legacy_formula = migrated.pop("formula", None)
        if "formulas" not in migrated:
            migrated["formulas"] = [] if legacy_formula is None else [legacy_formula]
        return migrated

    @property
    def formula(self) -> str | None:
        return self.formulas[0] if self.formulas else None

    @formula.setter
    def formula(self, value: str | None) -> None:
        if value is None:
            self.formulas = []
        elif self.formulas:
            self.formulas[0] = value
        else:
            self.formulas = [value]


class VbaModule(BaseModel):
    name: str
    code: str


class ButtonLink(BaseModel):
    sheet: str
    label: str | None = None
    macro: str


class Sheet(BaseModel):
    name: str
    used_range: str | None = None
    hidden: bool = False
    protected: bool = False
    hidden_cols: list[str] = Field(default_factory=list)
    hidden_rows: list[int] = Field(default_factory=list)
    cells: list[Cell] = Field(default_factory=list)
    merged: list[str] = Field(default_factory=list)
    validations: list[ValidationRule] = Field(default_factory=list)
    conditional_formats: list[ConditionalFormat] = Field(default_factory=list)


class Workbook(BaseModel):
    source_file: str
    sha256: str
    sheets: list[Sheet] = Field(default_factory=list)
    vba_modules: list[VbaModule] = Field(default_factory=list)
    buttons: list[ButtonLink] = Field(default_factory=list)
    defined_names: dict[str, str] = Field(default_factory=dict)
    external_refs: list[str] = Field(default_factory=list)
    extraction_gaps: list[str] = Field(default_factory=list)
