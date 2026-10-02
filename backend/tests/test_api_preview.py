import pytest

pytestmark = pytest.mark.snowflake

PARAMS = [
    {"name": "client", "label": "Client", "type": "client", "column": "CLIENT_NAME"},
    {"name": "period", "label": "Period", "type": "date_range", "column": "ORDER_DATE"},
]
VALUES = {"client": "Euro Shopping Channel", "period": {"start": "2004-01-01", "end": "2004-12-31"}}


def _preview(c, widget, values=VALUES):
    r = c.post("/api/widgets/preview", json={"widget": widget, "params": PARAMS, "values": values})
    assert r.status_code == 200, r.text
    return r.json()


def test_archetype_catalog(sf_designer):
    ids = {a["id"] for a in sf_designer.get("/api/archetypes").json()}
    assert {"aggregate", "time_series", "top_n", "share_of_total", "kpi_summary", "pivot"} <= ids


def test_preview_bar_with_params(sf_designer):
    d = _preview(
        sf_designer,
        {
            "id": "w1",
            "type": "bar",
            "title": "By line",
            "archetype": {"id": "aggregate", "params": {"dimensions": ["PRODUCT_LINE"], "measure": "SALES", "agg": "sum"}},
        },
    )
    assert d["error"] is None, d["error"]
    assert d["widget_id"] == "w1" and len(d["rows"]) == 7
    assert d["encoding"]["x"] == "PRODUCT_LINE"


def test_preview_error_is_200(sf_designer):
    d = _preview(
        sf_designer,
        {"id": "w2", "type": "bar", "archetype": {"id": "aggregate", "params": {"dimensions": ["NOPE"], "measure": "SALES"}}},
    )
    assert d["error"]


def test_preview_text_and_narrative(sf_designer):
    d = _preview(sf_designer, {"id": "t", "type": "heading", "options": {"text": "Hi"}})
    assert d["meta"]["text"] == "Hi"
    d = _preview(sf_designer, {"id": "n", "type": "text", "options": {"narrative": True}})
    assert "generated" in d["meta"]["text"]


def test_custom_archetypes(sf_designer):
    bad = sf_designer.post("/api/archetypes/custom", json={"name": "Bad", "sql": "DELETE FROM {{table}}"})
    assert bad.status_code == 400
    both = sf_designer.post("/api/archetypes/custom", json={"name": "X"})
    assert both.status_code == 400

    preset = sf_designer.post(
        "/api/archetypes/custom",
        json={
            "name": "Revenue by territory",
            "base": {"id": "aggregate", "params": {"dimensions": ["TERRITORY"], "measure": "SALES"}},
            "suggested_widgets": ["bar"],
        },
    )
    assert preset.status_code == 200, preset.text
    spec = preset.json()
    assert spec["kind"] == "custom" and spec["id"].startswith("custom:")

    sql = sf_designer.post(
        "/api/archetypes/custom",
        json={"name": "Status count", "sql": "SELECT STATUS, COUNT(*) AS N FROM {{table}} WHERE {{where}} GROUP BY 1 ORDER BY 2 DESC"},
    )
    assert sql.status_code == 200, sql.text

    ids = {a["id"] for a in sf_designer.get("/api/archetypes").json()}
    assert spec["id"] in ids and sql.json()["id"] in ids

    d = _preview(sf_designer, {"id": "c1", "type": "bar", "archetype": {"id": spec["id"], "params": {}}})
    assert d["error"] is None, d["error"]
    assert d["rows"]

    for s in (spec, sql.json()):
        assert sf_designer.delete(f"/api/archetypes/custom/{s['id'].removeprefix('custom:')}").json() == {"ok": True}
    assert spec["id"] not in {a["id"] for a in sf_designer.get("/api/archetypes").json()}
