"""Builtin archetypes. Ids and param names are a contract (seed reports + LLM target them).

Conventions:
- the single output measure column is aliased `VALUE`; dimension/date columns keep their names
- columns prefixed `__` are helpers read by `meta()` and dropped by the engine
- every query ends with `LIMIT <= ctx.max_rows`
"""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field

from app.archetypes.base import Archetype, CompileContext, CompiledQuery, register
from app.archetypes.sqlutil import (
    Agg,
    Grain,
    agg_sql,
    check_ident,
    grain_bucket_end,
    period_label,
    previous_window,
    trunc_sql,
)
from app.schemas.report import Encoding

# ---------------------------------------------------------------------------
# Shared param fields
# ---------------------------------------------------------------------------


def _measure() -> Any:
    return Field(
        description="Numeric column to aggregate (for count/count_distinct any column works)",
        examples=["SALES"],
    )


def _agg() -> Any:
    return Field(
        default="sum",
        description="Aggregation applied to the measure: sum, avg, count, count_distinct, min or max",
    )


def _date_column() -> Any:
    return Field(description="Date column used for the time axis", examples=["ORDER_DATE"])


def _limit(ctx: CompileContext, n: int | None = None) -> str:
    return f"LIMIT {min(int(n), ctx.max_rows) if n else ctx.max_rows}"


def _num(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        v = float(v)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _delta(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None or prev == 0:
        return None
    return (cur - prev) / abs(prev)


def _as_date(v: Any) -> date | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return v.date()
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _ranked_with_other(ctx: CompileContext, dim: str, value_expr: str, k: int) -> str:
    """dim, VALUE, __ORD: the top-k dim values by VALUE, everything else as one 'Other' row.

    'Other' is recomputed from raw rows so non-additive aggs (avg, count_distinct) stay exact.
    """
    return (
        f"WITH __B AS (SELECT {dim} AS __K, {value_expr} AS __V FROM {ctx.table} WHERE {ctx.where_sql} GROUP BY 1), "
        f"__R AS (SELECT __K, ROW_NUMBER() OVER (ORDER BY __V DESC NULLS LAST) AS __RN FROM __B) "
        f"SELECT CASE WHEN __R.__RN <= {k} THEN TO_VARCHAR({dim}) ELSE 'Other' END AS {dim}, "
        f"{value_expr} AS VALUE, MIN(__R.__RN) AS __ORD "
        f"FROM {ctx.table} JOIN __R ON EQUAL_NULL({dim}, __R.__K) "
        f"WHERE {ctx.where_sql} GROUP BY 1"
    )


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------


class AggregateParams(BaseModel):
    dimensions: list[str] = Field(
        min_length=1,
        max_length=2,
        description="1 or 2 columns to group by. With 2, the second becomes the series (long format)",
        examples=[["PRODUCT_LINE"], ["TERRITORY", "DEAL_SIZE"]],
    )
    measure: str = _measure()
    agg: Agg = _agg()
    sort: Literal["desc", "asc", "none"] = Field(
        default="desc", description="Sort by value (desc/asc) or by dimension (none)"
    )
    limit: int | None = Field(default=None, ge=1, description="Maximum number of rows (empty = all)")


@register
class AggregateArchetype(Archetype):
    id = "aggregate"
    name = "Group & aggregate"
    description = "Aggregate a measure grouped by one or two dimensions, e.g. total SALES by PRODUCT_LINE."
    Params = AggregateParams
    suggested_widgets = ["bar", "stacked_bar", "table", "pie", "donut"]
    example_params = {"dimensions": ["PRODUCT_LINE"], "measure": "SALES", "agg": "sum", "sort": "desc"}

    def compile(self, p: AggregateParams, ctx: CompileContext) -> CompiledQuery:
        dims = [ctx.col(d) for d in p.dimensions]
        m = ctx.col(p.measure)
        dl = ", ".join(dims)
        order = {"desc": "VALUE DESC NULLS LAST", "asc": "VALUE ASC NULLS LAST", "none": dl}[p.sort]
        sql = (
            f"SELECT {dl}, {agg_sql(p.agg, m)} AS VALUE FROM {ctx.table} WHERE {ctx.where_sql} "
            f"GROUP BY {dl} ORDER BY {order} {_limit(ctx, p.limit)}"
        )
        return CompiledQuery(sql, dict(ctx.bind))

    def encoding(self, p: AggregateParams) -> Encoding:
        dims = [check_ident(d) for d in p.dimensions]
        return Encoding(
            x=dims[0], y=["VALUE"], series=dims[1] if len(dims) > 1 else None, label=dims[0], value="VALUE"
        )


# ---------------------------------------------------------------------------
# time_series
# ---------------------------------------------------------------------------


class TimeSeriesParams(BaseModel):
    date_column: str = _date_column()
    measure: str = _measure()
    agg: Agg = _agg()
    grain: Grain = Field(default="month", description="Time bucket size")
    cumulative: bool = Field(default=False, description="Running total instead of per-period values")
    series: str | None = Field(
        default=None, description="Optional column that splits the line into one series per value", examples=["TERRITORY"]
    )


@register
class TimeSeriesArchetype(Archetype):
    id = "time_series"
    name = "Time series"
    description = "A measure aggregated per day/week/month/quarter/year, optionally cumulative or split by a series column."
    Params = TimeSeriesParams
    suggested_widgets = ["line", "area", "bar", "stacked_bar", "table"]
    example_params = {"date_column": "ORDER_DATE", "measure": "SALES", "agg": "sum", "grain": "month"}

    def compile(self, p: TimeSeriesParams, ctx: CompileContext) -> CompiledQuery:
        dc, m = ctx.col(p.date_column), ctx.col(p.measure)
        s = ctx.col(p.series) if p.series else None
        keys = f"{dc}, {s}" if s else dc
        # positional GROUP/ORDER BY: Snowflake resolves a bare "ORDER_DATE" to the raw column, not the alias
        pos = "1, 2" if s else "1"
        inner = (
            f"SELECT {trunc_sql(p.grain, dc)} AS {dc}{', ' + s if s else ''}, {agg_sql(p.agg, m)} AS VALUE "
            f"FROM {ctx.table} WHERE ({ctx.where_sql}) AND {dc} IS NOT NULL GROUP BY {pos}"
        )
        if p.cumulative:
            part = f"PARTITION BY {s} " if s else ""
            sql = (
                f"SELECT {keys}, SUM(VALUE) OVER ({part}ORDER BY {dc} ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) "
                f"AS VALUE FROM ({inner}) ORDER BY {keys} {_limit(ctx)}"
            )
        else:
            sql = f"{inner} ORDER BY {pos} {_limit(ctx)}"
        return CompiledQuery(sql, dict(ctx.bind))

    def encoding(self, p: TimeSeriesParams) -> Encoding:
        return Encoding(
            x=check_ident(p.date_column),
            y=["VALUE"],
            series=check_ident(p.series) if p.series else None,
            label=check_ident(p.date_column),
            value="VALUE",
        )


# ---------------------------------------------------------------------------
# top_n
# ---------------------------------------------------------------------------


class TopNParams(BaseModel):
    dimension: str = Field(description="Column to rank", examples=["CLIENT_NAME"])
    measure: str = _measure()
    agg: Agg = _agg()
    n: int = Field(default=10, ge=1, le=1000, description="How many top values to keep")
    include_other: bool = Field(default=False, description="Add one 'Other' row for everything outside the top n")


@register
class TopNArchetype(Archetype):
    id = "top_n"
    name = "Top N"
    description = "The top N values of a dimension ranked by an aggregated measure, optionally with an 'Other' row."
    Params = TopNParams
    suggested_widgets = ["bar", "table", "pie", "donut"]
    example_params = {"dimension": "CLIENT_NAME", "measure": "SALES", "agg": "sum", "n": 10}

    def compile(self, p: TopNParams, ctx: CompileContext) -> CompiledQuery:
        d, m = ctx.col(p.dimension), ctx.col(p.measure)
        v = agg_sql(p.agg, m)
        if p.include_other:
            sql = f"{_ranked_with_other(ctx, d, v, p.n)} ORDER BY __ORD {_limit(ctx)}"
        else:
            sql = (
                f"SELECT {d}, {v} AS VALUE FROM {ctx.table} WHERE {ctx.where_sql} GROUP BY {d} "
                f"ORDER BY VALUE DESC NULLS LAST {_limit(ctx, p.n)}"
            )
        return CompiledQuery(sql, dict(ctx.bind))

    def encoding(self, p: TopNParams) -> Encoding:
        d = check_ident(p.dimension)
        return Encoding(x=d, y=["VALUE"], label=d, value="VALUE")


# ---------------------------------------------------------------------------
# share_of_total
# ---------------------------------------------------------------------------


class ShareOfTotalParams(BaseModel):
    dimension: str = Field(description="Column whose values split the total", examples=["PRODUCT_LINE"])
    measure: str = _measure()
    agg: Agg = _agg()
    top_k: int | None = Field(
        default=6, ge=1, le=100, description="Keep the k largest slices and merge the rest into 'Other' (empty = all)"
    )


@register
class ShareOfTotalArchetype(Archetype):
    id = "share_of_total"
    name = "Share of total"
    description = "Each dimension value's share of the total (SHARE, 0-1), with small slices merged into 'Other'."
    Params = ShareOfTotalParams
    suggested_widgets = ["pie", "donut", "bar", "table"]
    example_params = {"dimension": "PRODUCT_LINE", "measure": "SALES", "agg": "sum", "top_k": 6}

    def compile(self, p: ShareOfTotalParams, ctx: CompileContext) -> CompiledQuery:
        d, m = ctx.col(p.dimension), ctx.col(p.measure)
        v = agg_sql(p.agg, m)
        if p.top_k:
            inner = _ranked_with_other(ctx, d, v, p.top_k)
            order = "__ORD"
        else:
            inner = f"SELECT {d}, {v} AS VALUE FROM {ctx.table} WHERE {ctx.where_sql} GROUP BY {d}"
            order = "VALUE DESC NULLS LAST"
        sql = (
            f"SELECT *, VALUE / NULLIF(SUM(VALUE) OVER (), 0) AS SHARE FROM ({inner}) "
            f"ORDER BY {order} {_limit(ctx)}"
        )
        return CompiledQuery(sql, dict(ctx.bind))

    def encoding(self, p: ShareOfTotalParams) -> Encoding:
        d = check_ident(p.dimension)
        return Encoding(x=d, y=["VALUE"], label=d, value="VALUE")


# ---------------------------------------------------------------------------
# period_over_period
# ---------------------------------------------------------------------------


class PeriodOverPeriodParams(BaseModel):
    date_column: str = _date_column()
    measure: str = _measure()
    agg: Agg = _agg()
    grain: Literal["month", "quarter", "year"] = Field(default="quarter", description="Period size")
    dimension: str | None = Field(
        default=None,
        description="Optional column: compare the current vs previous period per value of this column",
        examples=["PRODUCT_LINE"],
    )


@register
class PeriodOverPeriodArchetype(Archetype):
    id = "period_over_period"
    name = "Period over period"
    description = (
        "Change vs the previous period. Without a dimension: a time series with VALUE, PREVIOUS and "
        "CHANGE_PCT. With a dimension: current vs previous period per value (current = the report's "
        "date range, else the latest period in the data)."
    )
    Params = PeriodOverPeriodParams
    suggested_widgets = ["table", "bar", "line"]
    example_params = {"date_column": "ORDER_DATE", "measure": "SALES", "agg": "sum", "grain": "quarter"}

    def compile(self, p: PeriodOverPeriodParams, ctx: CompileContext) -> CompiledQuery:
        dc, m = ctx.col(p.date_column), ctx.col(p.measure)
        bind = dict(ctx.bind)
        g = p.grain
        rng = ctx.date_range
        if not p.dimension:
            if rng:
                bind.update(a_s=rng.start, a_e=rng.end)
                where = (
                    f"({ctx.where_sql_without_dates}) AND {dc} BETWEEN "
                    f"DATEADD({g}, -1, DATE_TRUNC('{g}', %(a_s)s::DATE)) AND %(a_e)s::DATE"
                )
                outer = f"WHERE {dc} >= DATE_TRUNC('{g}', %(a_s)s::DATE)"
            else:
                where, outer = f"({ctx.where_sql}) AND {dc} IS NOT NULL", ""
            sql = (
                f"WITH __B AS (SELECT {trunc_sql(g, dc)} AS {dc}, {agg_sql(p.agg, m)} AS VALUE "
                f"FROM {ctx.table} WHERE {where} GROUP BY 1), "
                f"__L AS (SELECT {dc}, VALUE, IFF(LAG({dc}) OVER (ORDER BY {dc}) = DATEADD({g}, -1, {dc}), "
                f"LAG(VALUE) OVER (ORDER BY {dc}), NULL) AS PREVIOUS FROM __B) "
                f"SELECT {dc}, VALUE, PREVIOUS, (VALUE - PREVIOUS) / NULLIF(ABS(PREVIOUS), 0) AS CHANGE_PCT "
                f"FROM __L {outer} ORDER BY {dc} {_limit(ctx)}"
            )
            return CompiledQuery(sql, bind)

        d = ctx.col(p.dimension)
        if rng:
            ps, pe = previous_window(rng.start, rng.end, "previous_period")
            bind.update(a_cs=rng.start, a_ce=rng.end, a_ps=ps, a_pe=pe)
            bounds = (
                "SELECT %(a_cs)s::DATE AS CS, %(a_ce)s::DATE AS CE, %(a_ps)s::DATE AS PS, %(a_pe)s::DATE AS PE"
            )
            base_where = ctx.where_sql_without_dates
        else:
            bounds = (
                f"SELECT CS, DATEADD(day, -1, DATEADD({g}, 1, CS)) AS CE, DATEADD({g}, -1, CS) AS PS, "
                f"DATEADD(day, -1, CS) AS PE FROM (SELECT DATE_TRUNC('{g}', MAX({dc}))::DATE AS CS "
                f"FROM {ctx.table} WHERE {ctx.where_sql})"
            )
            base_where = ctx.where_sql
        cur = f"{dc} BETWEEN __W.CS AND __W.CE"
        prev = f"{dc} BETWEEN __W.PS AND __W.PE"
        inner = (
            f"SELECT {d}, {agg_sql(p.agg, f'IFF({cur}, {m}, NULL)')} AS VALUE, "
            f"{agg_sql(p.agg, f'IFF({prev}, {m}, NULL)')} AS PREVIOUS, "
            f"MIN(__W.CS) AS __CS, MIN(__W.CE) AS __CE, MIN(__W.PS) AS __PS, MIN(__W.PE) AS __PE "
            f"FROM {ctx.table} CROSS JOIN ({bounds}) __W "
            f"WHERE ({base_where}) AND {dc} BETWEEN __W.PS AND __W.CE GROUP BY {d}"
        )
        sql = (
            f"SELECT *, (VALUE - PREVIOUS) / NULLIF(ABS(PREVIOUS), 0) AS CHANGE_PCT FROM ({inner}) "
            f"ORDER BY VALUE DESC NULLS LAST {_limit(ctx)}"
        )
        return CompiledQuery(sql, bind)

    def encoding(self, p: PeriodOverPeriodParams) -> Encoding:
        x = check_ident(p.dimension) if p.dimension else check_ident(p.date_column)
        return Encoding(x=x, y=["VALUE", "PREVIOUS"], label=x, value="VALUE")

    def meta(self, df: pd.DataFrame, p: PeriodOverPeriodParams, ctx: CompileContext) -> dict[str, Any]:
        if df.empty:
            return {}
        if p.dimension:
            cs, ce = _as_date(df["__CS"].iloc[0]), _as_date(df["__CE"].iloc[0])
            ps, pe = _as_date(df["__PS"].iloc[0]), _as_date(df["__PE"].iloc[0])
            additive = p.agg in ("sum", "count")
            cur = round(sum(_num(v) or 0.0 for v in df["VALUE"]), 6) if additive else None
            prv = round(sum(_num(v) or 0.0 for v in df["PREVIOUS"]), 6) if additive else None
            return {
                "period_label": period_label(cs, ce) if cs and ce else None,
                "previous_label": period_label(ps, pe) if ps and pe else None,
                "value": cur,
                "previous": prv,
                "delta_pct": _delta(cur, prv),
            }
        last = df.iloc[-1]
        start = _as_date(last[check_ident(p.date_column)])
        return {
            "period_label": period_label(start, grain_bucket_end(start, p.grain)) if start else None,
            "value": _num(last["VALUE"]),
            "previous": _num(last["PREVIOUS"]),
            "delta_pct": _num(last["CHANGE_PCT"]),
        }


# ---------------------------------------------------------------------------
# kpi_summary
# ---------------------------------------------------------------------------


class KpiSummaryParams(BaseModel):
    measure: str = _measure()
    agg: Agg = _agg()
    date_column: str | None = Field(
        default="ORDER_DATE", description="Date column used to find the comparison period (empty = no comparison)"
    )
    compare: Literal["previous_period", "previous_year", "none"] = Field(
        default="previous_period",
        description="Compare the report's date range with the equal-length period before it, or the same dates a year earlier",
    )


@register
class KpiSummaryArchetype(Archetype):
    id = "kpi_summary"
    name = "KPI summary"
    description = (
        "A single number (VALUE) with comparison against the previous period or previous year when the "
        "report has a date range. meta: value, previous, delta_pct, period_label."
    )
    Params = KpiSummaryParams
    suggested_widgets = ["kpi"]
    example_params = {"measure": "SALES", "agg": "sum", "date_column": "ORDER_DATE", "compare": "previous_period"}

    def _comparing(self, p: KpiSummaryParams, ctx: CompileContext) -> bool:
        return bool(p.date_column and ctx.date_range and p.compare != "none")

    def compile(self, p: KpiSummaryParams, ctx: CompileContext) -> CompiledQuery:
        m = ctx.col(p.measure)
        dc = ctx.col(p.date_column) if p.date_column else None
        bind = dict(ctx.bind)
        if self._comparing(p, ctx):
            rng = ctx.date_range
            ps, pe = previous_window(rng.start, rng.end, p.compare)
            bind.update(a_cs=rng.start, a_ce=rng.end, a_ps=ps, a_pe=pe)
            cur = f"{dc} BETWEEN %(a_cs)s::DATE AND %(a_ce)s::DATE"
            prev = f"{dc} BETWEEN %(a_ps)s::DATE AND %(a_pe)s::DATE"
            sql = (
                f"SELECT {agg_sql(p.agg, f'IFF({cur}, {m}, NULL)')} AS VALUE, "
                f"{agg_sql(p.agg, f'IFF({prev}, {m}, NULL)')} AS PREVIOUS "
                f"FROM {ctx.table} WHERE ({ctx.where_sql_without_dates}) AND (({cur}) OR ({prev})) {_limit(ctx, 1)}"
            )
        elif dc and not ctx.date_range:
            sql = (
                f"SELECT {agg_sql(p.agg, m)} AS VALUE, MIN({dc}) AS __MIN, MAX({dc}) AS __MAX "
                f"FROM {ctx.table} WHERE {ctx.where_sql} {_limit(ctx, 1)}"
            )
        else:
            sql = f"SELECT {agg_sql(p.agg, m)} AS VALUE FROM {ctx.table} WHERE {ctx.where_sql} {_limit(ctx, 1)}"
        return CompiledQuery(sql, bind)

    def encoding(self, p: KpiSummaryParams) -> Encoding:
        return Encoding(value="VALUE", y=["VALUE"])

    def meta(self, df: pd.DataFrame, p: KpiSummaryParams, ctx: CompileContext) -> dict[str, Any]:
        row = df.iloc[0] if not df.empty else {}
        value = _num(row.get("VALUE")) if len(row) else None
        out: dict[str, Any] = {"value": value, "previous": None, "delta_pct": None, "compare": "none"}
        rng = ctx.date_range
        if self._comparing(p, ctx):
            ps, pe = previous_window(rng.start, rng.end, p.compare)
            prev = _num(row.get("PREVIOUS")) if len(row) else None
            out.update(
                previous=prev,
                delta_pct=_delta(value, prev),
                compare=p.compare,
                period_label=period_label(rng.start, rng.end),
                previous_label=period_label(ps, pe),
            )
        elif rng:
            out["period_label"] = period_label(rng.start, rng.end)
        elif len(row) and "__MIN" in row:
            lo, hi = _as_date(row.get("__MIN")), _as_date(row.get("__MAX"))
            out["period_label"] = period_label(lo, hi) if lo and hi else "All time"
        else:
            out["period_label"] = "All time"
        return out


# ---------------------------------------------------------------------------
# moving_average
# ---------------------------------------------------------------------------


class MovingAverageParams(BaseModel):
    date_column: str = _date_column()
    measure: str = _measure()
    agg: Agg = _agg()
    grain: Grain = Field(default="month", description="Time bucket size")
    window: int = Field(default=3, ge=1, le=60, description="Number of periods in the trailing average")


@register
class MovingAverageArchetype(Archetype):
    id = "moving_average"
    name = "Moving average"
    description = "Per-period VALUE plus a trailing MOVING_AVG over the last `window` periods."
    Params = MovingAverageParams
    suggested_widgets = ["line", "area", "table"]
    example_params = {"date_column": "ORDER_DATE", "measure": "SALES", "agg": "sum", "grain": "month", "window": 3}

    def compile(self, p: MovingAverageParams, ctx: CompileContext) -> CompiledQuery:
        dc, m = ctx.col(p.date_column), ctx.col(p.measure)
        w = int(p.window)
        sql = (
            f"SELECT {dc}, VALUE, AVG(VALUE) OVER (ORDER BY {dc} ROWS BETWEEN {w - 1} PRECEDING AND CURRENT ROW) "
            f"AS MOVING_AVG FROM (SELECT {trunc_sql(p.grain, dc)} AS {dc}, {agg_sql(p.agg, m)} AS VALUE "
            f"FROM {ctx.table} WHERE ({ctx.where_sql}) AND {dc} IS NOT NULL GROUP BY 1) ORDER BY {dc} {_limit(ctx)}"
        )
        return CompiledQuery(sql, dict(ctx.bind))

    def encoding(self, p: MovingAverageParams) -> Encoding:
        x = check_ident(p.date_column)
        return Encoding(x=x, y=["VALUE", "MOVING_AVG"], label=x, value="VALUE")


# ---------------------------------------------------------------------------
# pivot
# ---------------------------------------------------------------------------


class PivotParams(BaseModel):
    row_dimension: str = Field(description="Column whose values become rows", examples=["TERRITORY"])
    column_dimension: str = Field(description="Column whose values become columns", examples=["PRODUCT_LINE"])
    measure: str = _measure()
    agg: Agg = _agg()
    max_columns: int = Field(default=12, ge=1, le=50, description="Keep only the largest column values")


@register
class PivotArchetype(Archetype):
    id = "pivot"
    name = "Pivot (cross-tab)"
    description = (
        "Cross-tab: one row per row_dimension value, one column per column_dimension value "
        "(largest max_columns kept). Works as a table or a stacked bar."
    )
    Params = PivotParams
    suggested_widgets = ["table", "stacked_bar", "bar"]
    example_params = {"row_dimension": "TERRITORY", "column_dimension": "PRODUCT_LINE", "measure": "SALES", "agg": "sum"}

    def compile(self, p: PivotParams, ctx: CompileContext) -> CompiledQuery:
        r, c, m = ctx.col(p.row_dimension), ctx.col(p.column_dimension), ctx.col(p.measure)
        sql = (
            f"WITH __B AS (SELECT {r}, {c}, {agg_sql(p.agg, m)} AS VALUE FROM {ctx.table} "
            f"WHERE {ctx.where_sql} GROUP BY {r}, {c}), "
            f"__T AS (SELECT {c} AS __C, SUM(VALUE) AS __TOT FROM __B GROUP BY 1 "
            f"ORDER BY __TOT DESC NULLS LAST LIMIT {int(p.max_columns)}) "
            f"SELECT __B.{r}, __B.{c}, __B.VALUE, __T.__TOT FROM __B JOIN __T ON EQUAL_NULL(__B.{c}, __T.__C) "
            f"ORDER BY __T.__TOT DESC NULLS LAST, __B.{r} {_limit(ctx)}"
        )
        return CompiledQuery(sql, dict(ctx.bind))

    def post_process(self, df: pd.DataFrame, p: PivotParams, ctx: CompileContext) -> pd.DataFrame:
        r, c = check_ident(p.row_dimension), check_ident(p.column_dimension)
        if df.empty:
            return pd.DataFrame(columns=[r])
        df = df.copy()
        df[r] = df[r].map(lambda v: "(null)" if v is None or (isinstance(v, float) and math.isnan(v)) else v)
        df[c] = df[c].map(lambda v: "(null)" if v is None or (isinstance(v, float) and math.isnan(v)) else str(v))
        df["VALUE"] = pd.to_numeric(df["VALUE"].map(_num), errors="coerce")
        col_order = list(dict.fromkeys(df[c]))  # already sorted by column total desc
        wide = df.pivot_table(index=r, columns=c, values="VALUE", aggfunc="sum", dropna=False)
        wide = wide.reindex(columns=col_order)
        wide = wide.sort_index().reset_index()
        wide.columns = [str(x) for x in wide.columns]
        return wide

    def encoding(self, p: PivotParams) -> Encoding:
        r = check_ident(p.row_dimension)
        return Encoding(x=r, y=[], label=r)

    def finalize_encoding(self, enc: Encoding, df: pd.DataFrame, p: PivotParams) -> Encoding:
        return enc.model_copy(update={"y": [c for c in df.columns if c != enc.x]})


# ---------------------------------------------------------------------------
# distribution
# ---------------------------------------------------------------------------


class DistributionParams(BaseModel):
    column: str = Field(description="Numeric column to bucket into a histogram", examples=["SALES"])
    bins: int = Field(default=10, ge=1, le=100, description="Number of equal-width buckets")


def _fmt_num(v: float | None) -> str:
    if v is None:
        return "?"
    a = abs(v)
    if a >= 1e6:
        return f"{v / 1e6:.1f}M"
    if a >= 1e3:
        return f"{v / 1e3:.1f}K"
    if a == int(a):
        return f"{int(v)}"
    return f"{v:.2f}"


@register
class DistributionArchetype(Archetype):
    id = "distribution"
    name = "Distribution (histogram)"
    description = "Histogram of a numeric column: equal-width buckets with BIN_LABEL, BIN_START, BIN_END and COUNT."
    Params = DistributionParams
    suggested_widgets = ["bar", "table"]
    example_params = {"column": "SALES", "bins": 10}

    def compile(self, p: DistributionParams, ctx: CompileContext) -> CompiledQuery:
        c = ctx.col(p.column)
        if ctx.columns and ctx.columns.get(check_ident(p.column)) not in (None, "number"):
            raise ValueError(f"distribution needs a numeric column; {p.column} is {ctx.columns[check_ident(p.column)]}")
        b = int(p.bins)
        sql = (
            f"WITH __S AS (SELECT MIN({c})::FLOAT AS __LO, MAX({c})::FLOAT AS __HI FROM {ctx.table} WHERE {ctx.where_sql}), "
            f"__V AS (SELECT IFF(__S.__HI = __S.__LO, 1, LEAST(WIDTH_BUCKET({c}, __S.__LO, __S.__HI, {b}), {b})) AS __BIN "
            f"FROM {ctx.table} CROSS JOIN __S WHERE ({ctx.where_sql}) AND {c} IS NOT NULL), "
            f"__G AS (SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) AS __BIN FROM TABLE(GENERATOR(ROWCOUNT => {b}))) "
            f"SELECT __G.__BIN AS BIN, __S.__LO + (__G.__BIN - 1) * (__S.__HI - __S.__LO) / {b} AS BIN_START, "
            f"__S.__LO + __G.__BIN * (__S.__HI - __S.__LO) / {b} AS BIN_END, COUNT(__V.__BIN) AS \"COUNT\" "
            f"FROM __G CROSS JOIN __S LEFT JOIN __V ON __V.__BIN = __G.__BIN "
            f"GROUP BY __G.__BIN, __S.__LO, __S.__HI ORDER BY __G.__BIN {_limit(ctx)}"
        )
        return CompiledQuery(sql, dict(ctx.bind))

    def post_process(self, df: pd.DataFrame, p: DistributionParams, ctx: CompileContext) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["BIN_LABEL", "BIN_START", "BIN_END", "COUNT"])
        df = df.copy()
        df["BIN_START"] = [None if _num(v) is None else round(_num(v), 6) for v in df["BIN_START"]]
        df["BIN_END"] = [None if _num(v) is None else round(_num(v), 6) for v in df["BIN_END"]]
        df["BIN_LABEL"] = [f"{_fmt_num(s)}–{_fmt_num(e)}" for s, e in zip(df["BIN_START"], df["BIN_END"])]
        return df[["BIN_LABEL", "BIN_START", "BIN_END", "COUNT"]]

    def encoding(self, p: DistributionParams) -> Encoding:
        return Encoding(x="BIN_LABEL", y=["COUNT"], label="BIN_LABEL", value="COUNT")
