"""Live archetype tests against DEMO_CORP.SALES.V_SALES (needs Snowflake credentials).

Credentials come from the environment, falling back to `export SNOWFLAKE_*=` lines in
~/.bashrc (non-interactive shells skip them). The token is never printed.
"""

from __future__ import annotations

import os
import re
import shlex

import pytest

from app.archetypes import engine
from app.archetypes.base import REGISTRY
from app.schemas.report import CustomArchetypeDef, DataSource, ParamDef, WidgetData, WidgetSpec

pytestmark = pytest.mark.snowflake

TABLE = "DEMO_CORP.SALES.V_SALES"
TOTAL_SALES = 10_032_628.85
TOTAL_ROWS = 2823
CLIENT = "Euro Shopping Channel"
PARAMS = [
    ParamDef(name="client", label="Client", type="client", column="CLIENT_NAME"),
    ParamDef(name="period", label="Period", type="date_range", column="ORDER_DATE"),
]
VALUES = {"client": CLIENT, "period": {"start": "2004-01-01", "end": "2004-12-31"}}


def _env_from_bashrc() -> None:
    rc = os.path.expanduser("~/.bashrc")
    if not os.path.exists(rc):
        return
    pat = re.compile(r"^\s*export\s+(SNOWFLAKE_[A-Z_]+)=(.*)$")
    with open(rc) as fh:
        for line in fh:
            m = pat.match(line)
            if m and not os.environ.get(m.group(1)):
                parts = shlex.split(m.group(2), comments=True)
                os.environ[m.group(1)] = parts[0] if parts else ""


@pytest.fixture(scope="module")
def client():
    _env_from_bashrc()
    e = os.environ
    if not all(e.get(k) for k in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_API")):
        pytest.skip("Snowflake credentials not configured")
    from app.snowflake.client import SnowflakeClient, SnowflakeCredentials

    c = SnowflakeClient(
        SnowflakeCredentials(
            account=e["SNOWFLAKE_ACCOUNT"],
            user=e["SNOWFLAKE_USER"],
            token=e["SNOWFLAKE_API"],
            warehouse=e.get("SNOWFLAKE_WAREHOUSE"),
            role=e.get("SNOWFLAKE_ROLE"),
        )
    )
    yield c
    c.close()


def run(client, aid: str, params: dict | None = None, values: dict | None = None, custom=None) -> WidgetData:
    a = REGISTRY.get(aid)
    p = {**(a.example_params if a else {}), **(params or {})}
    w = WidgetSpec(id=f"w_{aid}", type="table", archetype={"id": aid, "params": p})
    out = engine.execute_widget(
        client,
        w,
        param_defs=PARAMS,
        runtime_values=values or {},
        default_source=DataSource(table=TABLE),
        custom_archetypes=custom or {},
    )
    assert out.error is None, f"{aid}: {out.error}\n{out.sql}"
    assert out.sql
    return out


def scalar(client, sql: str, bind: dict | None = None) -> float:
    return float(client.query(sql, bind).iloc[0, 0] or 0)


@pytest.fixture(scope="module")
def client_2004(client) -> float:
    return scalar(
        client,
        f"SELECT SUM(SALES) FROM {TABLE} WHERE CLIENT_NAME = %(c)s AND ORDER_DATE BETWEEN '2004-01-01' AND '2004-12-31'",
        {"c": CLIENT},
    )


@pytest.fixture(scope="module")
def client_2003(client) -> float:
    return scalar(
        client,
        f"SELECT SUM(SALES) FROM {TABLE} WHERE CLIENT_NAME = %(c)s AND ORDER_DATE BETWEEN '2003-01-01' AND '2003-12-31'",
        {"c": CLIENT},
    )


def total(rows, col="VALUE") -> float:
    return sum(r[col] or 0 for r in rows)


def test_columns_described(client):
    cols = engine.table_columns(client, TABLE)
    assert cols["SALES"] == "number" and cols["ORDER_DATE"] == "date" and cols["CLIENT_NAME"] == "string"
    assert len(cols) == 24


def test_aggregate(client, client_2004):
    out = run(client, "aggregate")
    assert total(out.rows) == pytest.approx(TOTAL_SALES, abs=0.01)
    assert out.rows[0]["PRODUCT_LINE"] == "Classic Cars"
    vals = [r["VALUE"] for r in out.rows]
    assert vals == sorted(vals, reverse=True)
    out = run(client, "aggregate", values=VALUES)
    assert total(out.rows) == pytest.approx(client_2004, abs=0.01)
    out = run(client, "aggregate", {"dimensions": ["TERRITORY", "DEAL_SIZE"], "agg": "count"})
    assert total(out.rows) == TOTAL_ROWS and out.encoding.series == "DEAL_SIZE"


def test_time_series(client, client_2004):
    out = run(client, "time_series")
    dates = [r["ORDER_DATE"] for r in out.rows]
    assert len(dates) == len(set(dates)) == 29  # Jan 2003 .. May 2005
    assert total(out.rows) == pytest.approx(TOTAL_SALES, abs=0.01)
    out = run(client, "time_series", values=VALUES)
    assert all(r["ORDER_DATE"].startswith("2004-") for r in out.rows)
    assert total(out.rows) == pytest.approx(client_2004, abs=0.01)
    out = run(client, "time_series", {"cumulative": True, "grain": "year"})
    assert out.rows[-1]["VALUE"] == pytest.approx(TOTAL_SALES, abs=0.01)
    out = run(client, "time_series", {"series": "TERRITORY", "grain": "quarter"})
    assert out.encoding.series == "TERRITORY" and total(out.rows) == pytest.approx(TOTAL_SALES, abs=0.01)


def test_top_n(client):
    out = run(client, "top_n")
    assert len(out.rows) == 10 and out.rows[0]["CLIENT_NAME"] == CLIENT
    out = run(client, "top_n", {"n": 3, "include_other": True})
    assert [r["CLIENT_NAME"] for r in out.rows][-1] == "Other" and len(out.rows) == 4
    assert total(out.rows) == pytest.approx(TOTAL_SALES, abs=0.01)
    out = run(client, "top_n", values=VALUES)
    assert [r["CLIENT_NAME"] for r in out.rows] == [CLIENT]


def test_share_of_total(client):
    out = run(client, "share_of_total", {"top_k": 3})
    assert out.rows[-1]["PRODUCT_LINE"] == "Other" and len(out.rows) == 4
    assert total(out.rows, "SHARE") == pytest.approx(1.0, abs=1e-4)
    assert all(0 <= r["SHARE"] <= 1 for r in out.rows)
    out = run(client, "share_of_total", values=VALUES)
    assert total(out.rows, "SHARE") == pytest.approx(1.0, abs=1e-4)


def test_period_over_period(client, client_2004, client_2003):
    out = run(client, "period_over_period")
    assert [c.name for c in out.columns] == ["ORDER_DATE", "VALUE", "PREVIOUS", "CHANGE_PCT"]
    assert out.rows[0]["PREVIOUS"] is None
    for prev, cur in zip(out.rows, out.rows[1:]):
        assert cur["PREVIOUS"] == pytest.approx(prev["VALUE"])
    assert out.meta["period_label"] == "Q2 2005"
    out = run(client, "period_over_period", values=VALUES)
    assert all(r["ORDER_DATE"].startswith("2004-") for r in out.rows)
    assert total(out.rows) == pytest.approx(client_2004, abs=0.01)
    out = run(client, "period_over_period", {"dimension": "PRODUCT_LINE"}, values=VALUES)
    assert total(out.rows) == pytest.approx(client_2004, abs=0.01)
    assert total(out.rows, "PREVIOUS") == pytest.approx(client_2003, abs=0.01)
    assert out.meta["period_label"] == "2004" and out.meta["previous_label"] == "2003"
    out = run(client, "period_over_period", {"dimension": "PRODUCT_LINE"})
    assert out.meta["period_label"] == "Q2 2005" and out.meta["previous_label"] == "Q1 2005"


def test_kpi_summary(client, client_2004, client_2003):
    out = run(client, "kpi_summary")
    assert out.rows[0]["VALUE"] == pytest.approx(TOTAL_SALES, abs=0.01)
    assert out.meta["compare"] == "none" and out.meta["previous"] is None
    out = run(client, "kpi_summary", values=VALUES)
    assert out.rows[0]["VALUE"] > 0
    assert out.meta["value"] == pytest.approx(client_2004, abs=0.01)
    assert out.meta["previous"] == pytest.approx(client_2003, abs=0.01)
    assert out.meta["delta_pct"] == pytest.approx((client_2004 - client_2003) / client_2003)
    assert out.meta["period_label"] == "2004"
    out = run(client, "kpi_summary", {"compare": "previous_year", "agg": "count_distinct", "measure": "ORDER_NUMBER"}, values=VALUES)
    assert out.meta["value"] > 0 and out.meta["previous"] > 0


def test_moving_average(client):
    out = run(client, "moving_average")
    assert len(out.rows) == 29
    assert out.rows[0]["MOVING_AVG"] == pytest.approx(out.rows[0]["VALUE"])
    r = out.rows
    assert r[2]["MOVING_AVG"] == pytest.approx((r[0]["VALUE"] + r[1]["VALUE"] + r[2]["VALUE"]) / 3, rel=1e-6)
    run(client, "moving_average", values=VALUES)


def test_pivot(client):
    out = run(client, "pivot")
    assert out.encoding.x == "TERRITORY" and len(out.encoding.y) == 7
    grand = sum(sum((row[c] or 0) for c in out.encoding.y) for row in out.rows)
    assert grand == pytest.approx(TOTAL_SALES, abs=0.05)
    out = run(client, "pivot", {"max_columns": 3}, values=VALUES)
    assert len(out.encoding.y) == 3 and [r["TERRITORY"] for r in out.rows] == ["EMEA"]


def test_distribution(client):
    out = run(client, "distribution")
    assert len(out.rows) == 10 and total(out.rows, "COUNT") == TOTAL_ROWS
    assert [c.name for c in out.columns] == ["BIN_LABEL", "BIN_START", "BIN_END", "COUNT"]
    out = run(client, "distribution", {"bins": 5}, values=VALUES)
    assert len(out.rows) == 5 and total(out.rows, "COUNT") > 0


def test_custom_sql(client, client_2004):
    custom = {
        "c1": CustomArchetypeDef(
            id="c1",
            name="Shipped by line",
            sql="SELECT PRODUCT_LINE, SUM(SALES) AS S FROM {{table}} WHERE {{where}} "
            "AND STATUS LIKE 'Sh%' GROUP BY 1 ORDER BY 2 DESC",
        )
    }
    out = run(client, "custom:c1", values=VALUES, custom=custom)
    assert out.encoding.x == "PRODUCT_LINE" and out.encoding.y == ["S"]
    assert 0 < total(out.rows, "S") <= client_2004 + 0.01
