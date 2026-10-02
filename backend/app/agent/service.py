"""Agentic design: natural language -> WidgetSpec / ReportFormatBody, and run narratives.

The LLM only picks widget types, archetypes and their params from a catalog; it never writes SQL.
Its output is validated (pydantic + the archetype's Params model + column checks); validation
errors are fed back for at most `MAX_RETRIES` retries.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Literal

from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ValidationError

from app.agent import prompts
from app.agent.llm import LLMClient, LLMError, get_llm
from app.catalog import service as cat
from app.schemas.report import (
    ArchetypeConfig,
    ArchetypeSpec,
    DataSource,
    Filter,
    LayoutBox,
    ParamDef,
    ReportFormatBody,
    WidgetData,
    WidgetOptions,
    WidgetSpec,
)

log = logging.getLogger(__name__)

MAX_RETRIES = 2
WIDGET_TYPES = ["kpi", "table", "bar", "stacked_bar", "line", "area", "pie", "donut", "scatter", "text", "heading"]
FILTER_OPS = ["eq", "neq", "in", "gt", "gte", "lt", "lte", "between", "contains"]
COLUMN_PARAM_KEYS = {"measure", "dimension", "date_column", "series", "row_dimension", "column_dimension", "column"}
COLUMN_LIST_KEYS = {"dimensions"}
NUMBER_PARAM_KEYS = {"measure"}
DATE_PARAM_KEYS = {"date_column"}
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class AgentError(Exception):
    pass


# --- simplified LLM output -------------------------------------------------------------
class SimpleFilter(BaseModel):
    column: str
    op: Literal["eq", "neq", "in", "gt", "gte", "lt", "lte", "between", "contains"] = "eq"
    value: Any = None


class SimpleWidget(BaseModel):
    type: Literal["kpi", "table", "bar", "stacked_bar", "line", "area", "pie", "donut", "scatter", "text", "heading"]
    title: str = ""
    archetype_id: str | None = None
    archetype_params: dict[str, Any] = Field(default_factory=dict)
    filters: list[SimpleFilter] = Field(default_factory=list)
    narrative: bool = False
    text: str | None = None
    format: Literal["number", "currency", "percent", "compact"] | None = None


class SimpleParam(BaseModel):
    name: str
    label: str
    type: Literal["client", "select", "date_range", "string", "number"]
    column: str | None = None


def _widget_schema(archetype_ids: list[str], columns: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": WIDGET_TYPES},
            "title": {"type": "string"},
            "archetype_id": {"type": "string", "enum": [*archetype_ids, "none"]},
            "archetype_params": {"type": "object"},
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string", "enum": columns},
                        "op": {"type": "string", "enum": FILTER_OPS},
                        "value": {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "array", "items": {"type": "string"}}]},
                    },
                    "required": ["column", "op", "value"],
                },
            },
            "narrative": {"type": "boolean"},
            "text": {"type": "string"},
            "format": {"type": "string", "enum": ["number", "currency", "percent", "compact"]},
        },
        "required": ["type", "title", "archetype_id", "archetype_params"],
    }


def _report_schema(archetype_ids: list[str], columns: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"},
            "params": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "label": {"type": "string"},
                        "type": {"type": "string", "enum": ["client", "select", "date_range", "string", "number"]},
                        "column": {"type": "string", "enum": columns},
                    },
                    "required": ["name", "label", "type", "column"],
                },
            },
            "widgets": {"type": "array", "items": _widget_schema(archetype_ids, columns), "minItems": 4, "maxItems": 8},
            "explanation": {"type": "string"},
        },
        "required": ["name", "description", "params", "widgets", "explanation"],
    }


# --- validation ---------------------------------------------------------------
def _builtin_params_model(archetype_id: str):
    try:
        cat.get_engine()
        from app.archetypes.base import REGISTRY  # noqa: PLC0415

        arch = REGISTRY.get(archetype_id)
        return arch.Params if arch is not None else None
    except Exception:
        return None


def _norm_col(value: Any, colmap: dict[str, str]) -> Any:
    if isinstance(value, str) and value.upper() in colmap:
        return colmap[value.upper()]
    return value


def validate_simple_widget(
    raw: Any, archetypes: dict[str, ArchetypeSpec], col_types: dict[str, str]
) -> tuple[SimpleWidget | None, list[str]]:
    errors: list[str] = []
    if not isinstance(raw, dict):
        return None, ["Widget must be a JSON object"]
    raw = dict(raw)
    if raw.get("archetype_id") in ("none", "", "null"):
        raw["archetype_id"] = None
    if raw.get("format") in ("", None):
        raw.pop("format", None)
    try:
        w = SimpleWidget.model_validate(raw)
    except ValidationError as e:
        return None, [f"{'.'.join(map(str, er['loc']))}: {er['msg']}" for er in e.errors()]
    colmap = {c.upper(): c for c in col_types}

    if w.type in ("text", "heading"):
        w.archetype_id = None
        w.archetype_params = {}
        if w.type == "text" and not (w.text or "").strip():
            w.narrative = True
        return w, []

    if not w.archetype_id:
        return w, [f"Widget '{w.title}' of type {w.type} needs an archetype_id"]
    if w.archetype_id not in archetypes:
        return w, [f"Unknown archetype_id '{w.archetype_id}'. Choose one of: {', '.join(archetypes)}"]

    params = {k: v for k, v in (w.archetype_params or {}).items() if v is not None}
    for k, v in list(params.items()):
        if k in COLUMN_PARAM_KEYS:
            params[k] = v = _norm_col(v, colmap)
            if not isinstance(v, str) or v not in col_types:
                errors.append(f"archetype_params.{k}: '{v}' is not a column of the table")
            elif k in NUMBER_PARAM_KEYS and col_types[v] != "number" and params.get("agg") not in ("count", "count_distinct"):
                errors.append(f"archetype_params.{k}: '{v}' is not numeric; use a number column or agg count/count_distinct")
            elif k in DATE_PARAM_KEYS and col_types[v] != "date":
                errors.append(f"archetype_params.{k}: '{v}' is not a date column")
        elif k in COLUMN_LIST_KEYS:
            if isinstance(v, str):
                v = [v]
            v = [_norm_col(x, colmap) for x in (v or [])]
            params[k] = v
            bad = [x for x in v if x not in col_types]
            if bad:
                errors.append(f"archetype_params.{k}: {bad} are not columns of the table")

    model = _builtin_params_model(w.archetype_id)
    if model is not None:
        try:
            params = model.model_validate(params).model_dump(mode="json")
        except ValidationError as e:
            errors += [f"archetype_params.{'.'.join(map(str, er['loc']))}: {er['msg']}" for er in e.errors()]
    w.archetype_params = params

    for f in w.filters:
        f.column = _norm_col(f.column, colmap)
        if f.column not in col_types:
            errors.append(f"filters: '{f.column}' is not a column of the table")
        if f.op in ("in",) and not isinstance(f.value, list):
            f.value = [f.value]
        if f.op == "between" and not (isinstance(f.value, list) and len(f.value) == 2):
            errors.append("filters: 'between' needs value [low, high]")
    return w, errors


DEFAULT_SIZES: dict[str, tuple[int, int]] = {
    "heading": (12, 2),
    "text": (12, 3),
    "kpi": (3, 4),
    "table": (6, 8),
    "pie": (4, 7),
    "donut": (4, 7),
}


def default_size(widget_type: str) -> tuple[int, int]:
    return DEFAULT_SIZES.get(widget_type, (6, 7))


def to_widget_spec(w: SimpleWidget, table: str | None, layout: LayoutBox | None = None) -> WidgetSpec:
    wdt, hgt = default_size(w.type)
    options = WidgetOptions(narrative=w.narrative and w.type == "text", text=w.text or (w.title if w.type == "heading" else None))
    if w.format:
        options.format = w.format
    elif str(w.archetype_params.get("measure") or "").upper() in ("SALES", "REVENUE", "AMOUNT", "PRICE_EACH", "MSRP") and w.archetype_params.get("agg") not in ("count", "count_distinct"):
        options.format = "currency"
    return WidgetSpec(
        id=f"w_{uuid.uuid4().hex[:8]}",
        type=w.type,
        title=w.title,
        source=DataSource(table=table) if (table and w.archetype_id) else None,
        archetype=ArchetypeConfig(id=w.archetype_id, params=w.archetype_params) if w.archetype_id else None,
        filters=[Filter(column=f.column, op=f.op, value=f.value) for f in w.filters],
        layout=layout or LayoutBox(x=0, y=0, w=wdt, h=hgt),
        options=options,
    )


def pack_layout(widgets: list[WidgetSpec], start_y: int = 0, cols: int = 12) -> None:
    """Flow-pack widgets left to right on a 12-column grid (in place)."""
    x, y, row_h = 0, start_y, 0
    prev_kpi: bool | None = None
    for w in widgets:
        wdt, hgt = default_size(w.type)
        wdt = min(wdt, cols)
        is_kpi = w.type == "kpi"
        if x > 0 and (x + wdt > cols or (prev_kpi is not None and is_kpi != prev_kpi)):
            x, y, row_h = 0, y + row_h, 0
        prev_kpi = is_kpi
        w.layout = LayoutBox(x=x, y=y, w=wdt, h=hgt)
        x += wdt
        row_h = max(row_h, hgt)
    # Stretch a lone trailing widget in a row to fill remaining width for chart types.
    rows: dict[int, list[WidgetSpec]] = {}
    for w in widgets:
        rows.setdefault(w.layout.y, []).append(w)
    for row in rows.values():
        used = sum(w.layout.w for w in row)
        if used < cols and row[-1].type not in ("kpi",):
            row[-1].layout.w += cols - used
        elif used < cols and all(w.type == "kpi" for w in row):
            each = cols // len(row)
            for i, w in enumerate(row):
                w.layout.x, w.layout.w = i * each, each


# --- context ------------------------------------------------------------------
async def _context(company_id: str, table: str) -> tuple[dict, list[ArchetypeSpec], dict[str, str]]:
    profile = await run_in_threadpool(prompts.table_profile, company_id, table)
    archetypes = cat.list_archetypes(cat.custom_defs(company_id))
    col_types = {c["name"]: c["type"] for c in profile["columns"]}
    return profile, archetypes, col_types


def _params_text(params: list[ParamDef]) -> str:
    if not params:
        return ""
    items = [f"- {p.name} ({p.type}) filters column {p.column}" for p in params if p.column]
    return (
        "Runtime parameters of this report (applied automatically to every widget; do NOT add filters for them):\n"
        + "\n".join(items)
    )


async def _loop(llm: LLMClient, messages: list[dict], schema: dict, name: str, validate) -> Any:
    last_errors: list[str] = []
    for attempt in range(MAX_RETRIES + 1):
        try:
            raw = await llm.chat_json(messages, schema, name=name)
        except LLMError as e:
            last_errors = [str(e)]
            if "request failed" in str(e):
                raise AgentError(str(e)) from e
            messages = [*messages, {"role": "user", "content": f"Your reply was not valid JSON ({e}). Reply with JSON only."}]
            continue
        result, errors = validate(raw, final=attempt == MAX_RETRIES)
        if not errors:
            return result
        last_errors = errors
        log.info("agent attempt %d invalid: %s", attempt + 1, errors)
        messages = [
            *messages,
            {"role": "assistant", "content": json.dumps(raw)},
            {"role": "user", "content": "That JSON has problems:\n- " + "\n- ".join(errors[:12]) + "\nFix them and return the complete corrected JSON."},
        ]
    raise AgentError("The agent could not produce a valid design: " + "; ".join(last_errors[:6]))


# --- public API -----------------------------------------------------------------
async def design_widget(
    company_id: str, prompt: str, table: str, params: list[ParamDef], existing: list[WidgetSpec]
) -> tuple[WidgetSpec, str]:
    profile, archetypes, col_types = await _context(company_id, table)
    arch_map = {a.id: a for a in archetypes}
    user = "\n\n".join(
        x
        for x in [
            prompts.schema_text(profile),
            prompts.catalog_text(archetypes),
            prompts.WIDGET_GUIDE,
            _params_text(params),
            prompts.existing_widgets_text(existing),
            f"User request: {prompt}\n\nReturn JSON: {{type, title, archetype_id, archetype_params, filters, narrative, text, format}}.",
        ]
        if x
    )
    messages = [{"role": "system", "content": prompts.SYSTEM_WIDGET}, {"role": "user", "content": user}]

    def validate(raw, final=False):
        return validate_simple_widget(raw, arch_map, col_types)

    simple: SimpleWidget = await _loop(get_llm(company_id), messages, _widget_schema(list(arch_map), list(col_types)), "widget", validate)
    spec = to_widget_spec(simple, table)
    bottom = max((w.layout.y + w.layout.h for w in existing), default=0)
    spec.layout.y = bottom
    expl = f"Added a {simple.type} widget"
    if simple.archetype_id:
        expl += f" using the {arch_map[simple.archetype_id].name} archetype with {json.dumps(simple.archetype_params)}"
    if simple.filters:
        expl += f", filtered by {', '.join(f'{f.column} {f.op} {f.value}' for f in simple.filters)}"
    return spec, expl + "."


def _validate_params(raw_params: Any, col_types: dict[str, str]) -> tuple[list[ParamDef], list[str]]:
    out: list[ParamDef] = []
    errors: list[str] = []
    colmap = {c.upper(): c for c in col_types}
    seen: set[str] = set()
    for i, rp in enumerate(raw_params or []):
        try:
            sp = SimpleParam.model_validate(rp)
        except ValidationError as e:
            errors.append(f"params[{i}]: {e.errors()[0]['msg']}")
            continue
        sp.column = _norm_col(sp.column, colmap)
        name = re.sub(r"[^A-Za-z0-9_]", "_", sp.name.strip().lower()) or f"p{i}"
        if name in seen:
            continue
        if sp.column not in col_types:
            errors.append(f"params[{i}].column: '{sp.column}' is not a column")
            continue
        if sp.type == "date_range" and col_types[sp.column] != "date":
            errors.append(f"params[{i}]: date_range params need a date column, '{sp.column}' is {col_types[sp.column]}")
            continue
        seen.add(name)
        out.append(ParamDef(name=name, label=sp.label or name.title(), type=sp.type, column=sp.column))
    return out, errors


async def design_report(company_id: str, prompt: str, table: str) -> tuple[ReportFormatBody, str]:
    profile, archetypes, col_types = await _context(company_id, table)
    arch_map = {a.id: a for a in archetypes}
    user = "\n\n".join(
        [
            prompts.schema_text(profile),
            prompts.catalog_text(archetypes),
            prompts.WIDGET_GUIDE,
            "Report params are runtime arguments chosen when generating the report (e.g. a client and a date_range "
            "period); each filters every widget automatically via its column, so widgets must NOT filter on them. "
            "Use type 'client' for a client/customer name column and 'date_range' for a date column.",
            f"User request: {prompt}\n\nReturn JSON: {{name, description, params: [{{name, label, type, column}}], "
            "widgets: [4 to 8 items of {type, title, archetype_id, archetype_params, filters, narrative, text, format}], explanation}.",
        ]
    )
    messages = [{"role": "system", "content": prompts.SYSTEM_REPORT}, {"role": "user", "content": user}]

    def validate(raw, final=False):
        if not isinstance(raw, dict):
            return None, ["Reply must be a JSON object"]
        errors: list[str] = []
        params, perr = _validate_params(raw.get("params"), col_types)
        if not final:
            errors += perr
        widgets: list[SimpleWidget] = []
        for i, rw in enumerate(raw.get("widgets") or []):
            w, werr = validate_simple_widget(rw, arch_map, col_types)
            if werr:
                if not final:
                    errors += [f"widgets[{i}]: {e}" for e in werr]
            elif w is not None:
                widgets.append(w)
        widgets = widgets[:8]
        if len(widgets) < (3 if final else 4):
            errors.append(f"Need 4 to 8 valid widgets, got {len(widgets)}")
        name = str(raw.get("name") or "").strip() or "Untitled report"
        return (name, str(raw.get("description") or ""), params, widgets, str(raw.get("explanation") or "")), errors

    name, description, params, simples, explanation = await _loop(
        get_llm(company_id), messages, _report_schema(list(arch_map), list(col_types)), "report", validate
    )
    specs = [to_widget_spec(w, table) for w in simples]
    pack_layout(specs)
    body = ReportFormatBody(name=name, description=description, default_source=DataSource(table=table), params=params, widgets=specs)
    return body, explanation or f"Designed '{name}' with {len(specs)} widgets."


# --- narratives ---------------------------------------------------------------------
def _fmt_num(v: Any) -> str:
    if isinstance(v, (int, float)):
        if abs(v) >= 1_000_000:
            return f"{v / 1_000_000:,.2f}M"
        if abs(v) >= 10_000:
            return f"{v:,.0f}"
        return f"{v:,.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else f"{v:,}"
    return str(v)


def data_digest(widgets: list[WidgetSpec], data: dict[str, WidgetData], max_rows: int = 8) -> str:
    """Compact text digest of computed widget data for the narrative prompt."""
    parts = []
    for w in widgets:
        d = data.get(w.id)
        if d is None or d.error or w.type in ("text", "heading") or not d.rows:
            continue
        lines = [f"## {w.title or w.type} ({w.type})"]
        if w.type == "kpi":
            enc_val = d.encoding.value or (d.encoding.y[0] if d.encoding.y else None) or (d.columns[0].name if d.columns else None)
            val = d.rows[0].get(enc_val) if enc_val else None
            meta = {k: v for k, v in d.meta.items() if isinstance(v, (int, float, str)) and k != "sql"}
            lines.append(f"value={_fmt_num(val)} {json.dumps(meta, default=str)}")
        else:
            cols = [c.name for c in d.columns][:6]
            lines.append(" | ".join(cols))
            for r in d.rows[:max_rows]:
                lines.append(" | ".join(_fmt_num(r.get(c)) for c in cols))
            if len(d.rows) > max_rows:
                lines.append(f"... {len(d.rows) - max_rows} more rows")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def fallback_narrative(format_name: str, values: dict[str, Any], widgets: list[WidgetSpec], data: dict[str, WidgetData]) -> str:
    """Deterministic summary used when the LLM is unavailable."""
    scope = _scope_text(values)
    sentences = [f"This {format_name} report covers {scope}." if scope else f"This is the {format_name} report."]
    for w in widgets:
        d = data.get(w.id)
        if d is None or d.error or not d.rows or w.type in ("text", "heading"):
            continue
        if w.type == "kpi":
            key = d.encoding.value or (d.encoding.y[0] if d.encoding.y else None)
            val = d.rows[0].get(key) if key else None
            if val is not None:
                s = f"{w.title or 'The headline metric'} was {_fmt_num(val)}"
                delta = d.meta.get("delta_pct")
                if isinstance(delta, (int, float)):
                    s += f" ({'up' if delta >= 0 else 'down'} {abs(delta) * 100:.1f}% vs the previous period)"
                sentences.append(s + ".")
        elif w.type in ("bar", "pie", "donut", "table", "stacked_bar") and len(sentences) < 6:
            label = d.encoding.x or d.encoding.label or (d.columns[0].name if d.columns else None)
            value = d.encoding.value or (d.encoding.y[0] if d.encoding.y else None)
            if label and value and label in d.rows[0] and value in d.rows[0]:
                top = d.rows[0]
                sentences.append(f"In {w.title or 'the breakdown'}, the leading entry is {top[label]} at {_fmt_num(top[value])}.")
    return " ".join(sentences)


def _scope_text(values: dict[str, Any]) -> str:
    bits = []
    for k, v in values.items():
        if isinstance(v, dict) and "start" in v:
            bits.append(f"{v['start']} to {v['end']}")
        elif v not in (None, ""):
            bits.append(str(v))
    return ", ".join(bits)


async def write_narrative(
    format_name: str,
    values: dict[str, Any],
    widget: WidgetSpec,
    widgets: list[WidgetSpec],
    data: dict[str, WidgetData],
    company_id: str | None = None,
) -> tuple[str, str, str | None]:
    """Returns (text, source, model): source is 'llm' or 'fallback'; model is the provider label
    that wrote it (e.g. 'cortex:llama3.3-70b'), or None for the deterministic fallback."""
    digest = data_digest(widgets, data)
    if not digest:
        return fallback_narrative(format_name, values, widgets, data), "fallback", None
    guidance = (widget.options.text or "").strip()
    messages = [
        {
            "role": "system",
            "content": "You are a business analyst writing the executive summary of a client report. "
            "Write 3 to 5 sentences of plain prose (no headings, no bullet lists, no markdown tables). "
            "Use only numbers present in the data; round sensibly; mention the most important movements and leaders.",
        },
        {
            "role": "user",
            "content": f"Report: {format_name}\nScope: {_scope_text(values) or 'all data'}\n"
            + (f"Instructions: {guidance}\n" if guidance else "")
            + f"Widget title: {widget.title or 'Executive summary'}\n\nData:\n{digest}",
        },
    ]
    try:
        llm = get_llm(company_id)
        text = await llm.chat(messages, temperature=0.3, max_tokens=500)
        if len(text.strip()) < 20:
            raise LLMError("empty narrative")
        return text.strip(), "llm", llm.label
    except Exception as e:
        log.warning("narrative LLM failed, using fallback: %s", e)
        return fallback_narrative(format_name, values, widgets, data), "fallback", None
