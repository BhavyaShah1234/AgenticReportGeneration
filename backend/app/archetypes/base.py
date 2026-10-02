"""Archetype interface: a compute operation that shapes data before a widget renders it.

An archetype compiles (params + context) into one Snowflake SELECT, optionally
post-processes the DataFrame in pandas, and declares an `Encoding` so generic widgets
know which columns are x / y / label / value.

Contract used by the rest of the backend (implemented in `app.archetypes.engine`):

    execute_widget(client, widget, *, param_defs, runtime_values, default_source) -> WidgetData
    list_archetypes(company_id: str | None = None) -> list[ArchetypeSpec]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

import pandas as pd
from pydantic import BaseModel

from app.schemas.report import ArchetypeSpec, DateRange, Encoding, WidgetType


@dataclass
class CompileContext:
    """Everything an archetype needs besides its own params.

    `where_sql` already contains widget filters and runtime params (client, etc.) as
    pyformat placeholders whose values live in `bind`. The date-range runtime param is
    included in `where_sql` too, *and* exposed separately via `date_range`/`date_column`
    so period-comparison archetypes (kpi_summary, period_over_period) can rebuild it.
    `where_sql_without_dates` is the same filter set minus the date-range predicate.
    """

    table: str
    where_sql: str = "TRUE"
    where_sql_without_dates: str = "TRUE"
    bind: dict[str, Any] = field(default_factory=dict)
    date_range: DateRange | None = None
    date_column: str | None = None
    runtime_values: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompiledQuery:
    sql: str
    bind: dict[str, Any]


class Archetype(ABC):
    id: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    Params: ClassVar[type[BaseModel]]
    suggested_widgets: ClassVar[list[WidgetType]] = []
    example_params: ClassVar[dict[str, Any]] = {}

    @abstractmethod
    def compile(self, params: BaseModel, ctx: CompileContext) -> CompiledQuery: ...

    def post_process(self, df: pd.DataFrame, params: BaseModel, ctx: CompileContext) -> pd.DataFrame:
        return df

    @abstractmethod
    def encoding(self, params: BaseModel) -> Encoding: ...

    def meta(self, df: pd.DataFrame, params: BaseModel, ctx: CompileContext) -> dict[str, Any]:
        return {}

    @classmethod
    def spec(cls) -> ArchetypeSpec:
        return ArchetypeSpec(
            id=cls.id,
            name=cls.name,
            description=cls.description,
            params_schema=cls.Params.model_json_schema(),
            suggested_widgets=list(cls.suggested_widgets),
            example_params=dict(cls.example_params),
        )


REGISTRY: dict[str, Archetype] = {}


def register(cls: type[Archetype]) -> type[Archetype]:
    REGISTRY[cls.id] = cls()
    return cls
