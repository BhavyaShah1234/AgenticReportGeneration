"""Thin glue between the API and Agent C's archetype engine (`app.archetypes.engine`).

The engine is imported lazily so the app still starts while it is being written.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.db import engine as db_engine
from app.models import CustomArchetypeRow
from app.schemas.report import (
    ArchetypeSpec,
    CustomArchetypeDef,
    DataSource,
    DateRange,
    ParamDef,
    WidgetData,
    WidgetSpec,
)

DATA_LESS_TYPES = {"text", "heading"}


def get_engine():
    from app.archetypes import engine  # noqa: PLC0415  (lazy: owned by Agent C)

    return engine


def custom_defs(company_id: str, session: Session | None = None) -> list[CustomArchetypeDef]:
    def _q(s: Session) -> list[CustomArchetypeDef]:
        rows = s.exec(select(CustomArchetypeRow).where(CustomArchetypeRow.company_id == company_id)).all()
        return [CustomArchetypeDef.model_validate_json(r.def_json) for r in rows]

    if session is not None:
        return _q(session)
    with Session(db_engine) as s:
        return _q(s)


def custom_map(defs: list[CustomArchetypeDef]) -> dict[str, CustomArchetypeDef]:
    """Keyed by both `custom:<id>` and the bare `<id>` so lookups work either way."""
    out: dict[str, CustomArchetypeDef] = {}
    for d in defs:
        bare = d.id.removeprefix("custom:")
        out[f"custom:{bare}"] = d
        out[bare] = d
    return out


def list_archetypes(defs: list[CustomArchetypeDef]) -> list[ArchetypeSpec]:
    return get_engine().list_archetypes(defs)


def builtin_ids() -> set[str]:
    return {a.id for a in get_engine().list_archetypes([]) if a.kind == "builtin"}


def normalize_values(param_defs: list[ParamDef], values: dict[str, Any]) -> dict[str, Any]:
    """Validate/coerce runtime values to JSON-friendly shapes; fill defaults.

    date_range -> {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}, number -> float/int, others -> str.
    Raises ValueError with a readable message on bad input.
    """
    out = dict(values or {})
    for p in param_defs:
        v = out.get(p.name)
        if v in (None, "", {}) and p.default not in (None, ""):
            v = p.default
        if v in (None, "", {}):
            out.pop(p.name, None)
            continue
        if p.type == "date_range":
            try:
                dr = DateRange.model_validate(v)
            except Exception as e:
                raise ValueError(f"Param '{p.name}' must be {{start, end}} dates (YYYY-MM-DD)") from e
            if dr.end < dr.start:
                raise ValueError(f"Param '{p.name}': end date is before start date")
            out[p.name] = dr.model_dump(mode="json")
        elif p.type == "number":
            try:
                f = float(v)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Param '{p.name}' must be a number") from e
            out[p.name] = int(f) if f.is_integer() else f
        else:
            out[p.name] = str(v) if not isinstance(v, list) else [str(x) for x in v]
    return out


def missing_required(param_defs: list[ParamDef], values: dict[str, Any]) -> list[str]:
    return [p.label or p.name for p in param_defs if p.required and values.get(p.name) in (None, "", {})]


def execute(
    client,
    widget: WidgetSpec,
    *,
    param_defs: list[ParamDef],
    values: dict[str, Any],
    default_source: DataSource | None,
    customs: dict[str, CustomArchetypeDef],
) -> WidgetData:
    """Execute one data widget; never raises."""
    if widget.type in DATA_LESS_TYPES and widget.archetype is None:
        return WidgetData(widget_id=widget.id, meta={"text": widget.options.text or ""})
    if widget.archetype is None:
        return WidgetData(widget_id=widget.id, error="No archetype selected for this widget")
    try:
        return get_engine().execute_widget(
            client,
            widget,
            param_defs=param_defs,
            runtime_values=values,
            default_source=default_source,
            custom_archetypes=customs,
        )
    except Exception as e:  # engine promises not to raise; be defensive anyway
        return WidgetData(widget_id=widget.id, error=f"{type(e).__name__}: {e}"[:500])
