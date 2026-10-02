import os

import pytest

from tests.conftest import new_client, signup, snowflake_body

pytestmark = pytest.mark.snowflake


def test_connection_saved_without_token(sf_designer):
    r = sf_designer.get("/api/connection")
    body = r.json()
    assert body["connected"] is True
    assert body["account"] == os.environ["SNOWFLAKE_ACCOUNT"]
    assert body["default_table"] == "DEMO_CORP.SALES.V_SALES"
    assert body["last_tested_at"]
    assert "token" not in body and os.environ["SNOWFLAKE_API"] not in r.text
    assert sf_designer.get("/api/auth/me").json()["snowflake_connected"] is True


def test_connection_test_endpoint(sf_designer):
    r = sf_designer.post("/api/connection/test").json()
    assert r["ok"] is True and r["info"]["USER_NAME"]


def test_put_connection_bad_token_400():
    c = new_client()
    signup(c)
    r = c.put("/api/connection", json={**snowflake_body(), "token": "not-a-valid-token"})
    assert r.status_code == 400
    assert r.json()["detail"].startswith("Connection test failed")
    assert c.get("/api/connection").json()["connected"] is False


def test_viewer_cannot_change_connection(sf_designer, sf_domain):
    v = new_client()
    signup(v, domain=sf_domain, role="viewer")
    assert v.put("/api/connection", json=snowflake_body()).status_code == 403
    assert v.get("/api/connection").json()["connected"] is True


def test_schema_tables_columns_values(sf_designer):
    tables = sf_designer.get("/api/schema/tables")
    assert tables.status_code == 200, tables.text
    names = {t["table"]: t["kind"] for t in tables.json()}
    assert names.get("DEMO_CORP.SALES.V_SALES") == "VIEW"
    assert names.get("DEMO_CORP.SALES.ORDER_LINES") == "TABLE"
    assert not any(t.startswith("SNOWFLAKE") for t in names)

    cols = {c["name"]: c["type"] for c in sf_designer.get("/api/schema/columns", params={"table": "DEMO_CORP.SALES.V_SALES"}).json()}
    assert cols["SALES"] == "number" and cols["ORDER_DATE"] == "date" and cols["CLIENT_NAME"] == "string"
    assert len(cols) == 24

    vals = sf_designer.get("/api/schema/values", params={"table": "DEMO_CORP.SALES.V_SALES", "column": "CLIENT_NAME"}).json()
    assert len(vals) == 92 and "Euro Shopping Channel" in vals
    q = sf_designer.get(
        "/api/schema/values", params={"table": "DEMO_CORP.SALES.V_SALES", "column": "CLIENT_NAME", "q": "euro"}
    ).json()
    assert "Euro Shopping Channel" in q and len(q) < 10


def test_schema_rejects_bad_identifiers(sf_designer):
    bad = [
        {"table": "DEMO_CORP.SALES.V_SALES; DROP TABLE X", "column": "CLIENT_NAME"},
        {"table": "DEMO_CORP.SALES.V_SALES", "column": "CLIENT_NAME) --"},
        {"table": "V_SALES", "column": "CLIENT_NAME"},
    ]
    for p in bad:
        r = sf_designer.get("/api/schema/values", params=p)
        assert r.status_code == 400, (p, r.text)
    q = sf_designer.get(
        "/api/schema/values", params={"table": "DEMO_CORP.SALES.V_SALES", "column": "CLIENT_NAME", "q": "' OR 1=1 --"}
    )
    assert q.status_code == 200 and q.json() == []
