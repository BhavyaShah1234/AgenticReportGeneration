"""Shared contracts for report formats, widgets, archetypes and widget data.

This module is the single source of truth. `frontend/lib/types.ts` mirrors it by hand,
and `shared/schemas/*.json` is exported from it via `python -m app.schemas.export`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Runtime parameters (chosen when a report is generated)
# ---------------------------------------------------------------------------

ParamType = Literal["client", "select", "date_range", "string", "number"]


class ParamDef(BaseModel):
    """A runtime argument declared by a report format, e.g. client or time period.

    If `column` is set, the param is applied automatically as a filter to every widget
    whose source has that column (unless the widget lists it in `ignore_params`):
    - client/select/string/number -> `column = value`
    - date_range -> `column BETWEEN start AND end`
    """

    name: str = Field(description="Identifier, e.g. 'client', 'period'")
    label: str
    type: ParamType
    column: str | None = Field(default=None, description="Column filtered by this param, e.g. CLIENT_NAME")
    options_column: str | None = Field(
        default=None, description="Column whose distinct values populate a dropdown (defaults to `column`)"
    )
    required: bool = True
    default: Any = None


class DateRange(BaseModel):
    start: date
    end: date


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

WidgetType = Literal[
    "kpi", "table", "bar", "stacked_bar", "line", "area", "pie", "donut", "scatter", "text", "heading"
]

FilterOp = Literal["eq", "neq", "in", "gt", "gte", "lt", "lte", "between", "contains"]


class Filter(BaseModel):
    """Static widget-level filter. Exactly one of `value` / `param` should be set."""

    column: str
    op: FilterOp = "eq"
    value: Any = None
    param: str | None = Field(default=None, description="Bind to a runtime ParamDef by name instead of a literal")


class DataSource(BaseModel):
    table: str = Field(description="Fully-qualified table or view, e.g. DEMO_CORP.SALES.V_SALES")


class ArchetypeConfig(BaseModel):
    id: str = Field(description="Builtin archetype id (e.g. 'time_series') or 'custom:<id>'")
    params: dict[str, Any] = Field(default_factory=dict)


class LayoutBox(BaseModel):
    """Position on a 12-column react-grid-layout canvas (row height ~ 40px)."""

    x: int = 0
    y: int = 0
    w: int = 6
    h: int = 6


class WidgetOptions(BaseModel):
    """Presentation-only settings; never affect computation."""

    format: Literal["number", "currency", "percent", "compact"] = "number"
    color: str | None = None
    show_legend: bool = True
    show_labels: bool = False
    text: str | None = Field(default=None, description="Body for text/heading widgets (markdown allowed for text)")
    narrative: bool = Field(default=False, description="Text widget filled by the LLM at generation time")
    extra: dict[str, Any] = Field(default_factory=dict)


class WidgetSpec(BaseModel):
    id: str
    type: WidgetType
    title: str = ""
    source: DataSource | None = None
    archetype: ArchetypeConfig | None = None
    filters: list[Filter] = Field(default_factory=list)
    ignore_params: list[str] = Field(default_factory=list)
    layout: LayoutBox = Field(default_factory=LayoutBox)
    options: WidgetOptions = Field(default_factory=WidgetOptions)


# ---------------------------------------------------------------------------
# Report formats and runs
# ---------------------------------------------------------------------------


class ReportFormatBody(BaseModel):
    """Editable content of a report format (what the designer saves)."""

    name: str
    description: str = ""
    client_scope: str | None = Field(default=None, description="Optional client this format is tailored for")
    default_source: DataSource | None = None
    params: list[ParamDef] = Field(default_factory=list)
    widgets: list[WidgetSpec] = Field(default_factory=list)


class ReportFormat(ReportFormatBody):
    id: str
    company_id: str
    created_by: str
    version: int = 1
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Widget data (what an archetype returns and widgets render)
# ---------------------------------------------------------------------------

ColumnType = Literal["string", "number", "date"]


class ColumnInfo(BaseModel):
    name: str
    type: ColumnType


class Encoding(BaseModel):
    """Tells generic chart widgets which columns play which role.

    - bar/line/area/stacked_bar: x + y (one or more series columns) or x + y[0] + series (long format)
    - pie/donut: label + value
    - kpi: value (+ optional delta / previous in WidgetData.meta)
    - table: render all columns
    - scatter: x + y[0]
    """

    x: str | None = None
    y: list[str] = Field(default_factory=list)
    series: str | None = None
    label: str | None = None
    value: str | None = None


class WidgetData(BaseModel):
    widget_id: str
    columns: list[ColumnInfo] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    encoding: Encoding = Field(default_factory=Encoding)
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Archetype extras, e.g. {'previous': 123.0, 'delta_pct': 0.12, 'period_label': 'Q1 2004'}",
    )
    sql: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Archetype catalog
# ---------------------------------------------------------------------------


class CustomArchetypeDef(BaseModel):
    """A company-defined archetype. Exactly one of `base` / `sql` is set.

    - base: a preset of a builtin archetype with fixed params (widget params override them).
    - sql: a read-only SELECT template over `{{table}}` that may reference runtime params as
      `%(param_name)s` and the standard filters as `{{where}}`.
    """

    id: str
    name: str
    description: str = ""
    base: ArchetypeConfig | None = None
    sql: str | None = None
    suggested_widgets: list[WidgetType] = Field(default_factory=list)


class ArchetypeSpec(BaseModel):
    id: str
    name: str
    description: str
    kind: Literal["builtin", "custom"] = "builtin"
    params_schema: dict[str, Any] = Field(description="JSON schema of the params object (for UI forms + LLM)")
    suggested_widgets: list[WidgetType] = Field(default_factory=list)
    example_params: dict[str, Any] = Field(default_factory=dict)
