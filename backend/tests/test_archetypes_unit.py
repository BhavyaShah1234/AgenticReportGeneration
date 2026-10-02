"""Offline tests for archetype compilation, safety and the engine (no Snowflake)."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
import sqlglot

from app.archetypes import engine
from app.archetypes.base import REGISTRY, CompileContext
from app.archetypes.sqlutil import IdentifierError, period_label, previous_window, quote_table
from app.schemas.report import CustomArchetypeDef, DataSource, DateRange, ParamDef, WidgetSpec

TABLE = "DEMO_CORP.SALES.V_SALES"
COLUMNS = {
    **{c: "string" for c in ["CLIENT_NAME", "PRODUCT_LINE", "TERRITORY", "DEAL_SIZE", "STATUS", "COUNTRY"]},
    **{c: "number" for c in ["SALES", "QUANTITY_ORDERED", "PRICE_EACH", "MSRP", "YEAR"]},
    "ORDER_DATE": "date",
}
BUILTIN_IDS = {
    "aggregate",
    "time_series",
    "top_n",
    "share_of_total",
    "period_over_period",
    "kpi_summary",
    "moving_average",
    "pivot",
    "distribution",
}
RANGE = DateRange(start=date(2004, 1, 1), end=date(2004, 12, 31))

VARIANTS: dict[str, list[dict]] = {
    "aggregate": [{}, {"dimensions": ["TERRITORY", "DEAL_SIZE"], "sort": "none", "limit": 5}],
    "time_series": [{}, {"cumulative": True, "series": "TERRITORY", "grain": "quarter", "agg": "count_distinct"}],
    "top_n": [{}, {"include_other": True, "n": 3, "agg": "avg"}],
    "share_of_total": [{}, {"top_k": None}],
    "period_over_period": [{}, {"dimension": "PRODUCT_LINE", "grain": "year"}],
    "kpi_summary": [{}, {"compare": "previous_year"}, {"compare": "none"}, {"date_column": None}],
    "moving_average": [{}, {"window": 6, "grain": "week"}],
    "pivot": [{}, {"max_columns": 3}],
    "distribution": [{}, {"bins": 25}],
}


def _ctx(with_range: bool) -> CompileContext:
    where_nd = '("CLIENT_NAME" = %(_p0)s)'
    where = where_nd + (' AND ("ORDER_DATE" BETWEEN %(_p1_s)s::DATE AND %(_p1_e)s::DATE)' if with_range else "")
    bind = {"_p0": "Euro Shopping Channel"}
    if with_range:
        bind.update(_p1_s=RANGE.start, _p1_e=RANGE.end)
    return CompileContext(
        table=quote_table(TABLE),
        where_sql=where,
        where_sql_without_dates=where_nd,
        bind=bind,
        date_range=RANGE if with_range else None,
        date_column="ORDER_DATE" if with_range else None,
        columns=COLUMNS,
        max_rows=5000,
    )


def _parse(sql: str) -> sqlglot.exp.Expression:
    probe = re.sub(r"%\((\w+)\)s", "'2000-01-01'", sql)
    stmts = [s for s in sqlglot.parse(probe, read="snowflake") if s is not None]
    assert len(stmts) == 1
    assert isinstance(stmts[0], sqlglot.exp.Query)
    return stmts[0]


def test_all_builtins_registered():
    assert BUILTIN_IDS <= set(REGISTRY)


@pytest.mark.parametrize("aid", sorted(BUILTIN_IDS))
@pytest.mark.parametrize("with_range", [False, True])
def test_compile_parses_and_binds(aid: str, with_range: bool):
    a = REGISTRY[aid]
    for overrides in VARIANTS[aid]:
        params = a.Params.model_validate({**a.example_params, **overrides})
        q = a.compile(params, _ctx(with_range))
        _parse(q.sql)
        # values are bound, never interpolated
        assert "Euro Shopping Channel" not in q.sql
        assert "%(_p0)s" in q.sql
        for name in re.findall(r"%\((\w+)\)s", q.sql):
            assert name in q.bind, f"{aid}: unbound placeholder {name}"
        assert re.search(r"LIMIT \d+\s*$", q.sql), f"{aid}: missing trailing LIMIT"
        enc = a.encoding(params)
        assert enc.x or enc.value


def test_kpi_previous_window_binds():
    a = REGISTRY["kpi_summary"]
    q = a.compile(a.Params.model_validate({"measure": "SALES"}), _ctx(True))
    assert q.bind["a_cs"] == date(2004, 1, 1) and q.bind["a_ce"] == date(2004, 12, 31)
    assert q.bind["a_ps"] == date(2003, 1, 1) and q.bind["a_pe"] == date(2003, 12, 31)
    assert "_p1_s" not in q.sql  # the runtime date predicate is replaced by the comparison windows


INJECTIONS = [
    'SALES"; DROP TABLE X; --',
    "SALES; DROP TABLE X",
    "SALES) OR (1=1",
    "1SALES",
    "SA LES",
    "NOT_A_COLUMN",
    "",
]


@pytest.mark.parametrize("bad", INJECTIONS)
def test_identifier_injection_rejected(bad: str):
    ctx = _ctx(False)
    cases = [
        ("aggregate", {"dimensions": [bad], "measure": "SALES"}),
        ("aggregate", {"dimensions": ["PRODUCT_LINE"], "measure": bad}),
        ("time_series", {"date_column": bad, "measure": "SALES"}),
        *([("time_series", {"date_column": "ORDER_DATE", "measure": "SALES", "series": bad})] if bad else []),
        ("top_n", {"dimension": bad, "measure": "SALES"}),
        ("pivot", {"row_dimension": "TERRITORY", "column_dimension": bad, "measure": "SALES"}),
        ("distribution", {"column": bad}),
        ("kpi_summary", {"measure": bad}),
    ]
    for aid, raw in cases:
        a = REGISTRY[aid]
        with pytest.raises(ValueError):
            a.compile(a.Params.model_validate(raw), ctx)


@pytest.mark.parametrize("bad", ["DEMO_CORP.SALES.V_SALES; DROP TABLE X", 'A."B"', "A.B.C.D", "A..B", "x y"])
def test_table_injection_rejected(bad: str):
    with pytest.raises(IdentifierError):
        quote_table(bad)


def test_bad_enum_params_rejected():
    a = REGISTRY["time_series"]
    with pytest.raises(ValueError):
        a.Params.model_validate({"date_column": "ORDER_DATE", "measure": "SALES", "grain": "month'); DROP"})
    a = REGISTRY["aggregate"]
    with pytest.raises(ValueError):
        a.Params.model_validate({"dimensions": ["A"], "measure": "SALES", "agg": "sum(1)); --"})


def test_distribution_requires_numeric():
    a = REGISTRY["distribution"]
    with pytest.raises(ValueError):
        a.compile(a.Params.model_validate({"column": "CLIENT_NAME"}), _ctx(False))


def test_date_helpers():
    assert previous_window(date(2004, 1, 1), date(2004, 12, 31)) == (date(2003, 1, 1), date(2003, 12, 31))
    assert previous_window(date(2004, 4, 1), date(2004, 6, 30)) == (date(2004, 1, 1), date(2004, 3, 31))
    assert previous_window(date(2004, 3, 1), date(2004, 3, 31), "previous_year") == (date(2003, 3, 1), date(2003, 3, 31))
    assert previous_window(date(2004, 1, 10), date(2004, 1, 19)) == (date(2003, 12, 31), date(2004, 1, 9))
    assert period_label(date(2004, 1, 1), date(2004, 12, 31)) == "2004"
    assert period_label(date(2004, 4, 1), date(2004, 6, 30)) == "Q2 2004"
    assert period_label(date(2004, 2, 1), date(2004, 2, 29)) == "Feb 2004"


# ---------------------------------------------------------------------------
# Engine with a fake client
# ---------------------------------------------------------------------------


class FakeClient:
    def __init__(self, result: pd.DataFrame | None = None, fail: Exception | None = None):
        self.result = result if result is not None else pd.DataFrame({"VALUE": [Decimal("1.5")]})
        self.fail = fail
        self.calls: list[tuple[str, dict | None]] = []

    def query(self, sql, params=None, max_rows=None):
        if sql.startswith("DESCRIBE TABLE"):
            return pd.DataFrame({"name": list(COLUMNS), "type": [
                {"string": "VARCHAR(100)", "number": "NUMBER(10,2)", "date": "DATE"}[t] for t in COLUMNS.values()
            ]})
        self.calls.append((sql, params))
        if self.fail:
            raise self.fail
        return self.result


PARAMS = [
    ParamDef(name="client", label="Client", type="client", column="CLIENT_NAME"),
    ParamDef(name="period", label="Period", type="date_range", column="ORDER_DATE"),
    ParamDef(name="region", label="Region", type="select", column="NOT_IN_TABLE"),
]
VALUES = {"client": "Euro Shopping Channel", "period": {"start": "2004-01-01", "end": "2004-12-31"}, "region": "X"}


@pytest.fixture(autouse=True)
def _clear_cache():
    engine.clear_column_cache()
    yield


def _widget(aid="aggregate", params=None, **kw) -> WidgetSpec:
    a = REGISTRY.get(aid)
    return WidgetSpec(
        id="w1", type="bar", archetype={"id": aid, "params": params if params is not None else a.example_params}, **kw
    )


def _run(client, widget, values=VALUES, custom=None):
    return engine.execute_widget(
        client,
        widget,
        param_defs=PARAMS,
        runtime_values=values,
        default_source=DataSource(table=TABLE),
        custom_archetypes=custom or {},
    )


def test_engine_applies_params_and_converts_rows():
    df = pd.DataFrame(
        {
            "PRODUCT_LINE": ["Classic Cars", None],
            "VALUE": [Decimal("10.50"), float("nan")],
            "D": [date(2004, 1, 1), None],
        }
    )
    client = FakeClient(df)
    out = _run(client, _widget())
    assert out.error is None, out.error
    sql, bind = client.calls[-1]
    assert out.sql == sql
    assert '"CLIENT_NAME" = %(' in sql and '"ORDER_DATE" BETWEEN' in sql
    assert "NOT_IN_TABLE" not in sql  # param whose column is missing from the table is skipped
    assert "Euro Shopping Channel" in bind.values()
    assert out.rows == [
        {"PRODUCT_LINE": "Classic Cars", "VALUE": 10.5, "D": "2004-01-01"},
        {"PRODUCT_LINE": None, "VALUE": None, "D": None},
    ]
    assert {c.name: c.type for c in out.columns} == {"PRODUCT_LINE": "string", "VALUE": "number", "D": "date"}
    assert out.encoding.x == "PRODUCT_LINE" and out.encoding.y == ["VALUE"]


def test_engine_ignore_params_and_empty_values():
    client = FakeClient()
    _run(client, _widget(ignore_params=["client"]), values={"client": "A", "period": None})
    sql, _ = client.calls[-1]
    assert "CLIENT_NAME" not in sql.split("WHERE", 1)[1] and "BETWEEN" not in sql


def test_engine_widget_filters_bind_values():
    client = FakeClient()
    w = _widget(
        filters=[
            {"column": "STATUS", "op": "in", "value": ["Shipped", "Resolved"]},
            {"column": "DEAL_SIZE", "op": "eq", "param": "client"},
            {"column": "SALES", "op": "gte", "value": 100},
            {"column": "COUNTRY", "op": "contains", "value": "us'; drop"},
        ]
    )
    out = _run(client, w)
    assert out.error is None, out.error
    sql, bind = client.calls[-1]
    assert "Shipped" not in sql and "drop" not in sql
    assert {"Shipped", "Resolved", 100, "us'; drop", "Euro Shopping Channel"} <= set(bind.values())


def test_engine_never_raises():
    out = _run(FakeClient(), _widget(params={"dimensions": ['X"; DROP TABLE Y'], "measure": "SALES"}))
    assert out.error and "Invalid identifier" in out.error
    out = _run(FakeClient(), _widget(params={"dimensions": [], "measure": "SALES"}))
    assert out.error and out.error.startswith("Invalid archetype params")
    out = _run(FakeClient(fail=RuntimeError("boom")), _widget())
    assert out.error == "boom" and out.sql  # sql is set once compiled
    out = _run(FakeClient(), WidgetSpec(id="w", type="bar", archetype={"id": "nope", "params": {}}))
    assert "Unknown archetype" in out.error
    out = engine.execute_widget(
        FakeClient(), _widget(), param_defs=[], runtime_values={}, default_source=None, custom_archetypes={}
    )
    assert "No data source" in out.error
    out = _run(FakeClient(), WidgetSpec(id="h", type="heading", title="Hi"))
    assert out.error is None and out.rows == []


def test_kpi_meta():
    client = FakeClient(pd.DataFrame({"VALUE": [Decimal("120")], "PREVIOUS": [Decimal("100")]}))
    out = _run(client, _widget("kpi_summary"))
    assert out.error is None, out.error
    assert out.meta["value"] == 120 and out.meta["previous"] == 100
    assert out.meta["delta_pct"] == pytest.approx(0.2)
    assert out.meta["period_label"] == "2004" and out.meta["previous_label"] == "2003"


def test_custom_archetypes():
    custom = {
        "big": CustomArchetypeDef(id="big", name="Big deals", base={"id": "top_n", "params": {"n": 3}}),
        "sql1": CustomArchetypeDef(
            id="sql1",
            name="Lines",
            sql="SELECT PRODUCT_LINE, SUM(SALES) AS S FROM {{table}} WHERE {{where}} AND STATUS LIKE 'Sh%' "
            "AND CLIENT_NAME = %(client)s GROUP BY 1",
        ),
    }
    client = FakeClient(pd.DataFrame({"PRODUCT_LINE": ["A"], "S": [Decimal("3")]}))
    w = WidgetSpec(
        id="w", type="bar", archetype={"id": "custom:big", "params": {"dimension": "PRODUCT_LINE", "measure": "SALES"}}
    )
    out = _run(client, w, custom=custom)
    assert out.error is None, out.error
    assert "LIMIT 3" in client.calls[-1][0]

    w = WidgetSpec(id="w", type="bar", archetype={"id": "custom:sql1", "params": {}})
    out = _run(client, w, custom=custom)
    assert out.error is None, out.error
    sql, bind = client.calls[-1]
    assert sql.startswith("SELECT * FROM (") and sql.endswith("LIMIT 5000")
    assert '"DEMO_CORP"."SALES"."V_SALES"' in sql and "LIKE 'Sh%%'" in sql
    assert bind["client"] == "Euro Shopping Channel"
    assert out.encoding.x == "PRODUCT_LINE" and out.encoding.y == ["S"]


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM {{table}}",
        "SELECT 1; DROP TABLE X",
        "INSERT INTO t SELECT * FROM {{table}}",
        "CREATE TABLE x AS SELECT 1",
        "UPDATE t SET a = 1",
        "GRANT ROLE x TO USER y",
        "",
        "SELECT FROM WHERE",
        "SELECT * FROM {{other}}",
    ],
)
def test_validate_custom_sql_rejects(sql: str):
    with pytest.raises(ValueError):
        engine.validate_custom_sql(sql)


def test_validate_custom_sql_accepts():
    engine.validate_custom_sql("WITH a AS (SELECT * FROM {{table}} WHERE {{where}}) SELECT COUNT(*) FROM a;")
    engine.validate_custom_sql("SELECT 1 UNION ALL SELECT 2")


def test_list_archetypes():
    specs = engine.list_archetypes(
        [
            CustomArchetypeDef(id="p", name="Preset", base={"id": "time_series", "params": {"grain": "year"}}),
            CustomArchetypeDef(id="s", name="SQL", sql="SELECT 1"),
        ]
    )
    ids = [s.id for s in specs]
    assert BUILTIN_IDS <= set(ids) and ids[-2:] == ["custom:p", "custom:s"]
    by_id = {s.id: s for s in specs}
    assert by_id["custom:p"].kind == "custom"
    assert "date_column" in by_id["custom:p"].params_schema["properties"]
    assert by_id["custom:s"].params_schema == {"type": "object", "properties": {}}
    for aid in BUILTIN_IDS:
        props = by_id[aid].params_schema["properties"]
        assert all("description" in v for v in props.values()), aid
