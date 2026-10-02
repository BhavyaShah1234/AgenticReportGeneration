"""Compact context for the LLM: table schema summary and archetype catalog."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from app.schemas.report import ArchetypeSpec, WidgetSpec
from app.snowflake import service as sf

MAX_SAMPLE_VALUES = 8
LOW_CARDINALITY = 40
_TTL_S = 1800

_cache: dict[tuple[str, str], tuple[float, dict]] = {}
_lock = threading.Lock()


def table_profile(company_id: str, table: str) -> dict[str, Any]:
    """{table, columns: [{name, type, samples?}], row_count}. Cached; blocking (run in threadpool)."""
    tbl = sf.qualified(table)
    key = (company_id, tbl)
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < _TTL_S:
            return hit[1]
    cols = sf.list_columns(company_id, tbl)
    client = sf.get_client(company_id)
    strings = [c["name"] for c in cols if c["type"] == "string"]
    dates = [c["name"] for c in cols if c["type"] == "date"]
    profile: dict[str, Any] = {"table": tbl, "columns": [dict(c) for c in cols], "row_count": None}
    parts = ["COUNT(*) AS \"__ROWS\""]
    for c in strings:
        parts.append(f'COUNT(DISTINCT {sf.validate_ident(c)}) AS "{c}"')
    for c in dates:
        parts.append(f'MIN({sf.validate_ident(c)}) AS "{c}__MIN"')
        parts.append(f'MAX({sf.validate_ident(c)}) AS "{c}__MAX"')
    stats = client.query(f"SELECT {', '.join(parts)} FROM {tbl}").iloc[0].to_dict()
    profile["row_count"] = sf.jsonable(stats.get("__ROWS"))
    low = [c for c in strings if (stats.get(c) or 0) <= LOW_CARDINALITY]
    samples: dict[str, list] = {}
    if low:
        union = " UNION ALL ".join(
            f"(SELECT '{c}' AS COL, TO_VARCHAR({sf.validate_ident(c)}) AS V FROM {tbl} "
            f"WHERE {sf.validate_ident(c)} IS NOT NULL GROUP BY 2 ORDER BY COUNT(*) DESC LIMIT {MAX_SAMPLE_VALUES})"
            for c in low
        )
        df = client.query(union)
        for _, r in df.iterrows():
            samples.setdefault(str(r["COL"]), []).append(str(r["V"]))
    for c in profile["columns"]:
        n = c["name"]
        if c["type"] == "string":
            c["distinct"] = sf.jsonable(stats.get(n))
            if n in samples:
                c["samples"] = samples[n]
        elif c["type"] == "date":
            c["min"] = sf.jsonable(stats.get(f"{n}__MIN"))
            c["max"] = sf.jsonable(stats.get(f"{n}__MAX"))
    with _lock:
        _cache[key] = (time.time(), profile)
    return profile


def schema_text(profile: dict[str, Any]) -> str:
    lines = [f"Table {profile['table']} ({profile.get('row_count')} rows). Columns:"]
    for c in profile["columns"]:
        extra = ""
        if c.get("samples"):
            extra = f" values e.g. {', '.join(repr(v) for v in c['samples'])}"
        elif c["type"] == "string" and c.get("distinct"):
            extra = f" ({c['distinct']} distinct values)"
        elif c["type"] == "date" and c.get("min"):
            extra = f" from {c['min']} to {c['max']}"
        lines.append(f"- {c['name']} [{c['type']}]{extra}")
    return "\n".join(lines)


def _param_summary(schema: dict) -> str:
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    defs = schema.get("$defs", {})
    out = []
    for name, p in props.items():
        p = _resolve(p, defs)
        t = p.get("type") or "/".join(x.get("type", "?") for x in p.get("anyOf", []) if isinstance(x, dict))
        enum = p.get("enum") or next((x.get("enum") for x in p.get("anyOf", []) if isinstance(x, dict) and x.get("enum")), None)
        desc = f"{name}: {'|'.join(map(str, enum)) if enum else t}"
        if t == "array" and isinstance(p.get("items"), dict):
            desc = f"{name}: list[{p['items'].get('type', 'string')}]"
        if "default" in p:
            desc += f" = {json.dumps(p['default'])}"
        elif name in required:
            desc += " (required)"
        out.append(desc)
    return "; ".join(out)


def _resolve(p: dict, defs: dict) -> dict:
    if "$ref" in p:
        return defs.get(p["$ref"].split("/")[-1], p)
    if "allOf" in p and len(p["allOf"]) == 1 and "$ref" in p["allOf"][0]:
        merged = dict(defs.get(p["allOf"][0]["$ref"].split("/")[-1], {}))
        merged.update({k: v for k, v in p.items() if k != "allOf"})
        return merged
    if "anyOf" in p:
        p = {**p, "anyOf": [_resolve(x, defs) if isinstance(x, dict) else x for x in p["anyOf"]]}
    return p


def catalog_text(archetypes: list[ArchetypeSpec]) -> str:
    lines = ["Archetypes (compute operations; pick one per data widget):"]
    for a in archetypes:
        lines.append(
            f"- {a.id}: {a.description} Params: {{{_param_summary(a.params_schema)}}}. "
            f"Suggested widgets: {', '.join(a.suggested_widgets) or 'any'}."
            + (f" Example params: {json.dumps(a.example_params)}" if a.example_params else "")
        )
    return "\n".join(lines)


def existing_widgets_text(widgets: list[WidgetSpec]) -> str:
    if not widgets:
        return ""
    items = [f"- {w.type} '{w.title}'" + (f" ({w.archetype.id})" if w.archetype else "") for w in widgets[:20]]
    return "Widgets already on the canvas (avoid duplicating them):\n" + "\n".join(items)


WIDGET_GUIDE = """Widget types: kpi (single number card; use kpi_summary), line/area (trends over time; use time_series or moving_average), bar/stacked_bar (category comparison; use aggregate, top_n, period_over_period, distribution), pie/donut (share; use share_of_total), table (detail; use top_n, aggregate or pivot), scatter, text (prose; set narrative=true for an AI-written executive summary, no archetype), heading (section title, no archetype).
Rules: use ONLY column names from the schema, spelled exactly. Measures must be number columns. date_column must be a date column. Never write SQL.
Revenue/sales means the SALES column if it exists. "Orders" means count_distinct of ORDER_NUMBER when present."""


SYSTEM_WIDGET = """You are a reporting assistant that designs ONE dashboard widget from a user request.
You output JSON only. You never write SQL; you choose a widget type and an archetype (a predefined computation) with its params."""

SYSTEM_REPORT = """You are a reporting assistant that designs a complete, reusable report format (a dashboard of 4 to 8 widgets) from a user request.
You output JSON only. You never write SQL; for each widget you choose a widget type and an archetype (a predefined computation) with its params.
Start with one heading widget and, when useful, a narrative text widget (narrative=true). Then add KPI cards and charts."""
