"""Widget execution engine: WidgetSpec + runtime params -> one safe Snowflake query -> WidgetData.

Public API (used by routes, runs and the agent):

    execute_widget(client, widget, *, param_defs, runtime_values, default_source, custom_archetypes) -> WidgetData
    list_archetypes(custom) -> list[ArchetypeSpec]
    validate_custom_sql(sql) -> None          # raises ValueError
    table_columns(client, table) -> dict[str, "string"|"number"|"date"]   # cached per table
    describe_columns(client, table) -> list[ColumnInfo]
"""

from __future__ import annotations

import math
import re
import threading
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

import pandas as pd
import sqlglot
from pydantic import BaseModel, ValidationError
from sqlglot import exp

import app.archetypes.builtins  # noqa: F401  (registers builtin archetypes)
from app.archetypes.base import REGISTRY, Archetype, CompileContext, CompiledQuery
from app.archetypes.sqlutil import IDENT_RE, col, normalize_table, quote_table
from app.config import get_settings
from app.schemas.report import (
    ArchetypeSpec,
    ColumnInfo,
    ColumnType,
    CustomArchetypeDef,
    DataSource,
    DateRange,
    Encoding,
    Filter,
    ParamDef,
    WidgetData,
    WidgetSpec,
)

# ---------------------------------------------------------------------------
# Table column cache
# ---------------------------------------------------------------------------

_COL_CACHE: dict[tuple[str, str], dict[str, str]] = {}
_COL_LOCK = threading.Lock()


def _sf_type(t: str) -> ColumnType:
    t = (t or "").upper()
    if t.startswith(("NUMBER", "DECIMAL", "NUMERIC", "INT", "BIGINT", "SMALLINT", "TINYINT", "FLOAT", "DOUBLE", "REAL", "FIXED")):
        return "number"
    if t.startswith(("DATE", "TIMESTAMP", "DATETIME")):
        return "date"
    return "string"


def table_columns(client: Any, table: str) -> dict[str, str]:
    """UPPERCASE column name -> 'string' | 'number' | 'date'. Cached per (account, table)."""
    key = (str(getattr(getattr(client, "creds", None), "account", id(client))), normalize_table(table))
    with _COL_LOCK:
        if key in _COL_CACHE:
            return _COL_CACHE[key]
    df = client.query(f"DESCRIBE TABLE {quote_table(table)}")
    lower = {c.lower(): c for c in df.columns}
    name_c, type_c = lower.get("name"), lower.get("type")
    if name_c is None:
        raise RuntimeError(f"Could not describe table {table}")
    cols = {str(r[name_c]).upper(): _sf_type(str(r[type_c]) if type_c else "") for _, r in df.iterrows()}
    if not cols:
        raise ValueError(f"Table {table} has no columns or does not exist")
    with _COL_LOCK:
        _COL_CACHE[key] = cols
    return cols


def describe_columns(client: Any, table: str) -> list[ColumnInfo]:
    return [ColumnInfo(name=n, type=t) for n, t in table_columns(client, table).items()]  # type: ignore[arg-type]


def clear_column_cache() -> None:
    with _COL_LOCK:
        _COL_CACHE.clear()


# ---------------------------------------------------------------------------
# Runtime values / filters -> WHERE
# ---------------------------------------------------------------------------


def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (list, tuple, set, dict)) and len(v) == 0:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    return False


def _to_date_range(v: Any) -> DateRange | None:
    if isinstance(v, DateRange):
        return v
    if isinstance(v, dict) and v.get("start") and v.get("end"):
        return DateRange.model_validate({"start": v["start"], "end": v["end"]})
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(v):
        return DateRange(start=v[0], end=v[1])
    return None


def _scalar(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool, Decimal, date, datetime)) or v is None:
        return v
    raise ValueError(f"Unsupported filter value {v!r}")


def _filter_pred(c: str, op: str, v: Any, key: str, bind: dict[str, Any]) -> str | None:
    rng = _to_date_range(v) if isinstance(v, (dict, DateRange)) else None
    if rng is not None or op == "between":
        rng = rng or _to_date_range(v)
        if rng is not None:
            bind[f"{key}_s"], bind[f"{key}_e"] = rng.start, rng.end
        elif isinstance(v, (list, tuple)) and len(v) == 2:
            bind[f"{key}_s"], bind[f"{key}_e"] = _scalar(v[0]), _scalar(v[1])
        else:
            raise ValueError(f"'between' filter on {c} needs [low, high] or {{start, end}}")
        return f"{c} BETWEEN %({key}_s)s AND %({key}_e)s"
    if op == "in" or (op == "eq" and isinstance(v, (list, tuple, set))):
        vals = list(v) if isinstance(v, (list, tuple, set)) else [v]
        if not vals:
            return None
        names = []
        for j, item in enumerate(vals):
            bind[f"{key}_{j}"] = _scalar(item)
            names.append(f"%({key}_{j})s")
        return f"{c} IN ({', '.join(names)})"
    if v is None:
        return f"{c} IS NULL" if op == "eq" else f"{c} IS NOT NULL" if op == "neq" else None
    bind[key] = _scalar(v)
    ph = f"%({key})s"
    match op:
        case "eq":
            return f"{c} = {ph}"
        case "neq":
            return f"({c} <> {ph} OR {c} IS NULL)"
        case "gt":
            return f"{c} > {ph}"
        case "gte":
            return f"{c} >= {ph}"
        case "lt":
            return f"{c} < {ph}"
        case "lte":
            return f"{c} <= {ph}"
        case "contains":
            return f"CONTAINS(LOWER(TO_VARCHAR({c})), LOWER({ph}))"
    raise ValueError(f"Unsupported filter op {op!r}")


def build_context(
    widget: WidgetSpec,
    table: str,
    columns: dict[str, str],
    param_defs: list[ParamDef],
    runtime_values: dict[str, Any],
    max_rows: int,
) -> CompileContext:
    bind: dict[str, Any] = {}
    preds: list[str] = []
    nodate: list[str] = []
    date_range: DateRange | None = None
    date_column: str | None = None
    defs = {p.name: p for p in param_defs}

    for i, f in enumerate(widget.filters):
        f = f if isinstance(f, Filter) else Filter.model_validate(f)
        c = col(f.column, columns)
        if f.param:
            v = runtime_values.get(f.param, defs[f.param].default if f.param in defs else None)
            if _is_empty(v):
                continue
        else:
            v = f.value
        pred = _filter_pred(c, f.op, v, f"_f{i}", bind)
        if pred:
            preds.append(pred)
            nodate.append(pred)

    ignore = set(widget.ignore_params)
    for i, p in enumerate(param_defs):
        if not p.column or p.name in ignore or not IDENT_RE.match(p.column):
            continue
        cu = p.column.upper()
        if columns and cu not in columns:
            continue
        v = runtime_values.get(p.name, p.default)
        if _is_empty(v):
            continue
        c = f'"{cu}"'
        key = f"_p{i}"
        if p.type == "date_range":
            rng = _to_date_range(v)
            if rng is None:
                raise ValueError(f"Parameter {p.name!r} needs {{start, end}} dates, got {v!r}")
            bind[f"{key}_s"], bind[f"{key}_e"] = rng.start, rng.end
            pred = f"{c} BETWEEN %({key}_s)s::DATE AND %({key}_e)s::DATE"
            preds.append(pred)
            if date_range is None:
                date_range, date_column = rng, cu
            else:
                nodate.append(pred)
            continue
        if p.type == "number" and not isinstance(v, (list, tuple)):
            v = float(v)
        pred = _filter_pred(c, "in" if isinstance(v, (list, tuple)) else "eq", v, key, bind)
        if pred:
            preds.append(pred)
            nodate.append(pred)

    return CompileContext(
        table=quote_table(table),
        where_sql=" AND ".join(f"({x})" for x in preds) or "TRUE",
        where_sql_without_dates=" AND ".join(f"({x})" for x in nodate) or "TRUE",
        bind=bind,
        date_range=date_range,
        date_column=date_column,
        runtime_values=dict(runtime_values),
        columns=columns,
        max_rows=max_rows,
    )


# ---------------------------------------------------------------------------
# Custom archetypes
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"%\((\w+)\)s")
_FORBIDDEN = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Command,
    exp.Commit,
    exp.Rollback,
    exp.Transaction,
    exp.Use,
    exp.Copy,
    exp.TruncateTable,
    exp.Set,
    exp.Grant,
)


def validate_custom_sql(sql: str) -> None:
    """Raise ValueError unless `sql` is exactly one read-only SELECT (or WITH ... SELECT)."""
    if not sql or not sql.strip():
        raise ValueError("SQL is empty")
    probe = sql.replace("{{table}}", "__TABLE__").replace("{{where}}", "TRUE")
    probe = _PLACEHOLDER_RE.sub("NULL", probe)
    if "{{" in probe or "}}" in probe:
        raise ValueError("Only {{table}} and {{where}} templates are supported")
    try:
        stmts = [s for s in sqlglot.parse(probe, read="snowflake") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise ValueError(f"SQL does not parse: {str(e).splitlines()[0]}") from e
    if len(stmts) != 1:
        raise ValueError(f"Exactly one statement is allowed, found {len(stmts)}")
    stmt = stmts[0]
    if not isinstance(stmt, exp.Query):
        raise ValueError(f"Only SELECT / WITH queries are allowed, got {stmt.key.upper()}")
    for node in stmt.walk():
        if isinstance(node, _FORBIDDEN):
            raise ValueError(f"Statement type {node.key.upper()} is not allowed in a read-only query")


def _custom_lookup(aid: str, custom: dict[str, CustomArchetypeDef]) -> CustomArchetypeDef | None:
    short = aid.removeprefix("custom:")
    return custom.get(short) or custom.get(aid) or next((c for c in custom.values() if c.id == short), None)


def _bind_value(v: Any) -> Any:
    if isinstance(v, dict) or isinstance(v, DateRange):
        rng = _to_date_range(v)
        if rng:
            return rng.start
    if isinstance(v, (list, tuple)):
        raise ValueError("List values cannot be bound into custom SQL")
    return v


def _compile_custom_sql(cdef: CustomArchetypeDef, ctx: CompileContext, runtime_values: dict[str, Any]) -> CompiledQuery:
    raw = cdef.sql or ""
    validate_custom_sql(raw)
    bind = dict(ctx.bind)
    for name in set(_PLACEHOLDER_RE.findall(raw)):
        if name in runtime_values:
            bind[name] = _bind_value(runtime_values[name])
        elif name.endswith(("_start", "_end")) and isinstance(runtime_values.get(name.rsplit("_", 1)[0]), (dict, DateRange)):
            rng = _to_date_range(runtime_values[name.rsplit("_", 1)[0]])
            bind[name] = (rng.start if name.endswith("_start") else rng.end) if rng else None
        else:
            bind[name] = None
    body = raw.strip().rstrip(";")
    body = re.sub(r"%(?!\(\w+\)s)", "%%", body)  # literal % must be doubled for pyformat
    body = body.replace("{{table}}", ctx.table).replace("{{where}}", f"({ctx.where_sql})")
    sql = f"SELECT * FROM ({body}) LIMIT {ctx.max_rows}"
    if not bind:
        sql = sql.replace("%%", "%")  # no interpolation happens without binds
    return CompiledQuery(sql, bind)


def _infer_encoding(columns: list[ColumnInfo]) -> Encoding:
    x = next((c.name for c in columns if c.type in ("string", "date")), None)
    ys = [c.name for c in columns if c.type == "number" and c.name != x]
    return Encoding(x=x, y=ys, label=x, value=ys[0] if ys else None)


# ---------------------------------------------------------------------------
# Result conversion
# ---------------------------------------------------------------------------


def _json_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, Decimal):
        f = float(v)
        return int(v) if v == v.to_integral_value() and abs(f) < 2**53 else f
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(v, int):
        return v
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else (v.date().isoformat() if v == v.normalize() else v.isoformat())
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (date, time)):
        return v.isoformat()
    if hasattr(v, "item"):  # numpy scalar
        return _json_value(v.item())
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v if isinstance(v, (str, list, dict)) else str(v)


def _infer_type(name: str, raw: pd.Series, table_cols: dict[str, str], enc: Encoding) -> ColumnType:
    for v in raw:
        if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT:
            continue
        if isinstance(v, bool):
            return "string"
        if isinstance(v, (int, float, Decimal)) or (hasattr(v, "dtype") and getattr(v, "dtype").kind in "iuf"):
            return "number"
        if isinstance(v, (date, datetime, pd.Timestamp)):
            return "date"
        return "string"
    if name in table_cols:
        return table_cols[name]  # type: ignore[return-value]
    return "number" if name in enc.y or name == enc.value else "string"


def _to_widget_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    cols = list(df.columns)
    return [{c: _json_value(v) for c, v in zip(cols, row)} for row in df.itertuples(index=False, name=None)]


def _format_error(e: Exception) -> str:
    if isinstance(e, ValidationError):
        parts = []
        for err in e.errors():
            loc = ".".join(str(x) for x in err.get("loc", ())) or "params"
            parts.append(f"{loc}: {err.get('msg')}")
        return "Invalid archetype params: " + "; ".join(parts)
    msg = str(e).strip() or type(e).__name__
    return msg if len(msg) < 1000 else msg[:1000] + "…"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def execute_widget(
    client: Any,
    widget: WidgetSpec,
    *,
    param_defs: list[ParamDef],
    runtime_values: dict,
    default_source: DataSource | None,
    custom_archetypes: dict[str, CustomArchetypeDef] | None = None,
) -> WidgetData:
    """Compile + run one widget. Never raises: failures land in `WidgetData.error`."""
    out = WidgetData(widget_id=widget.id)
    try:
        if widget.archetype is None:
            if widget.type in ("text", "heading"):
                return out
            raise ValueError("Widget has no archetype configured")
        source = widget.source or default_source
        if source is None or not source.table:
            raise ValueError("No data source: set the widget's source or the report's default source")
        quote_table(source.table)  # validate before touching Snowflake
        runtime_values = dict(runtime_values or {})
        custom_archetypes = custom_archetypes or {}
        max_rows = get_settings().max_rows

        columns = table_columns(client, source.table)
        ctx = build_context(widget, source.table, columns, param_defs or [], runtime_values, max_rows)

        aid = widget.archetype.id
        archetype: Archetype | None = None
        params: BaseModel | None = None
        if aid in REGISTRY:
            archetype = REGISTRY[aid]
            params = archetype.Params.model_validate(widget.archetype.params or {})
            compiled = archetype.compile(params, ctx)
        else:
            cdef = _custom_lookup(aid, custom_archetypes)
            if cdef is None:
                raise ValueError(f"Unknown archetype {aid!r}")
            if cdef.base is not None:
                if cdef.base.id not in REGISTRY:
                    raise ValueError(f"Custom archetype {cdef.id!r} uses unknown base {cdef.base.id!r}")
                archetype = REGISTRY[cdef.base.id]
                merged = {**(cdef.base.params or {}), **(widget.archetype.params or {})}
                params = archetype.Params.model_validate(merged)
                compiled = archetype.compile(params, ctx)
            elif cdef.sql:
                compiled = _compile_custom_sql(cdef, ctx, runtime_values)
            else:
                raise ValueError(f"Custom archetype {cdef.id!r} has neither base nor sql")
        out.sql = compiled.sql

        df = client.query(compiled.sql, compiled.bind or None, max_rows=max_rows)
        df.columns = [str(c) for c in df.columns]
        meta: dict[str, Any] = {}
        if archetype is not None and params is not None:
            df = archetype.post_process(df, params, ctx)
            meta = archetype.meta(df, params, ctx)
            enc = archetype.encoding(params)
        else:
            enc = Encoding()
        df = df[[c for c in df.columns if not str(c).startswith("__")]]

        out.columns = [ColumnInfo(name=c, type=_infer_type(c, df[c], columns, enc)) for c in df.columns]
        if archetype is not None and params is not None:
            enc = archetype.finalize_encoding(enc, df, params)
        else:
            enc = _infer_encoding(out.columns)
        out.encoding = enc
        out.rows = _to_widget_rows(df)
        out.meta = {k: _json_value(v) for k, v in meta.items()}
        if len(out.rows) >= max_rows:
            out.meta["truncated"] = True
    except Exception as e:  # noqa: BLE001 — contract: never raise
        out.error = _format_error(e)
    return out


def list_archetypes(custom: list[CustomArchetypeDef] | None = None) -> list[ArchetypeSpec]:
    specs = [type(a).spec() for a in REGISTRY.values()]
    for c in custom or []:
        base = REGISTRY.get(c.base.id) if c.base else None
        specs.append(
            ArchetypeSpec(
                id=c.id if c.id.startswith("custom:") else f"custom:{c.id}",
                name=c.name,
                description=c.description or (f"Preset of {base.name}" if base else "Custom SQL"),
                kind="custom",
                params_schema=base.Params.model_json_schema() if base else {"type": "object", "properties": {}},
                suggested_widgets=list(c.suggested_widgets) or (list(base.suggested_widgets) if base else ["table"]),
                example_params=dict(c.base.params) if c.base else {},
            )
        )
    return specs
