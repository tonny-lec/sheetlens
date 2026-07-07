from __future__ import annotations

from pydantic import BaseModel, Field

Primitive = str | int | float | bool | None


class Cell(BaseModel):
    ref: str
    value: Primitive = None
    formula: str | None = None


class ValidationRule(BaseModel):
    ranges: list[str]
    type: str
    formula1: str | None = None
    choices: list[str] = Field(default_factory=list)


class ConditionalFormat(BaseModel):
    range: str
    rule_type: str
    operator: str | None = None
    formula: str | None = None
    stop_if_true: bool = False


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
