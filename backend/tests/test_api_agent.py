import pytest

from app.agent.llm import extract_json, strip_think
from app.agent.service import pack_layout, validate_simple_widget
from app.schemas.report import ArchetypeSpec, WidgetSpec

COLS = {"ORDER_DATE": "date", "SALES": "number", "CLIENT_NAME": "string", "PRODUCT_LINE": "string", "ORDER_NUMBER": "number"}


def _arch():
    from app.catalog.service import list_archetypes

    return {a.id: a for a in list_archetypes([])}


def test_strip_think_and_extract_json():
    assert strip_think("<think>hmm</think>\nHello") == "Hello"
    assert extract_json('<think>x</think>```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"b": [1,2]} done') == {"b": [1, 2]}


def test_validate_simple_widget_good_and_bad():
    arch = _arch()
    w, errs = validate_simple_widget(
        {"type": "line", "title": "Monthly", "archetype_id": "time_series",
         "archetype_params": {"date_column": "order_date", "measure": "SALES", "grain": "month"}},
        arch, COLS,
    )
    assert errs == [] and w.archetype_params["date_column"] == "ORDER_DATE"
    _, errs = validate_simple_widget(
        {"type": "line", "title": "x", "archetype_id": "time_series", "archetype_params": {"date_column": "SALES", "measure": "REVENUE"}},
        arch, COLS,
    )
    assert any("not a date column" in e for e in errs) and any("REVENUE" in e for e in errs)
    _, errs = validate_simple_widget({"type": "bar", "title": "x", "archetype_id": "nope", "archetype_params": {}}, arch, COLS)
    assert errs and "Unknown archetype_id" in errs[0]
    w, errs = validate_simple_widget({"type": "text", "title": "Summary", "archetype_id": "none", "archetype_params": {}}, arch, COLS)
    assert errs == [] and w.narrative is True


def test_pack_layout():
    ws = [WidgetSpec(id=str(i), type=t) for i, t in enumerate(["heading", "kpi", "kpi", "line", "bar", "pie", "table"])]
    pack_layout(ws)
    for w in ws:
        assert 0 <= w.layout.x and w.layout.x + w.layout.w <= 12
    assert ws[0].layout.w == 12 and ws[1].layout.y == ws[0].layout.h
    assert ws[1].layout.w == 6 and ws[2].layout.x == 6  # two KPIs share the row evenly


@pytest.mark.llm
def test_agent_health(sf_designer):
    r = sf_designer.get("/api/agent/health").json()
    assert r["ok"] is True, r


@pytest.mark.llm
@pytest.mark.snowflake
def test_agent_widget_monthly_revenue(sf_designer):
    r = sf_designer.post(
        "/api/agent/widget",
        json={"prompt": "Show monthly revenue as a line chart", "table": "DEMO_CORP.SALES.V_SALES"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    w = body["widget"]
    assert w["type"] in ("line", "area")
    assert w["archetype"]["id"] in ("time_series", "moving_average")
    assert w["archetype"]["params"]["measure"] == "SALES"
    assert w["archetype"]["params"]["date_column"] == "ORDER_DATE"
    assert w["source"]["table"] == "DEMO_CORP.SALES.V_SALES"
    assert body["explanation"]
    # it must also execute
    d = sf_designer.post("/api/widgets/preview", json={"widget": w, "params": [], "values": {}}).json()
    assert d["error"] is None and d["rows"]


@pytest.mark.llm
@pytest.mark.snowflake
def test_agent_widget_top_clients(sf_designer):
    r = sf_designer.post("/api/agent/widget", json={"prompt": "Top 5 clients by sales as a bar chart"})
    assert r.status_code == 200, r.text
    w = r.json()["widget"]
    assert w["type"] in ("bar", "table")
    p = w["archetype"]["params"]
    assert w["archetype"]["id"] in ("top_n", "aggregate")
    assert "CLIENT_NAME" in (p.get("dimension"), *(p.get("dimensions") or []))


@pytest.mark.llm
@pytest.mark.snowflake
def test_agent_report(sf_designer):
    r = sf_designer.post("/api/agent/report", json={"prompt": "A quarterly account review for one client: KPIs, monthly trend and product mix"})
    assert r.status_code == 200, r.text
    fmt = r.json()["format"]
    assert 3 <= len(fmt["widgets"]) <= 8
    assert fmt["default_source"]["table"] == "DEMO_CORP.SALES.V_SALES"
    for w in fmt["widgets"]:
        lay = w["layout"]
        assert lay["x"] + lay["w"] <= 12
        if w["type"] not in ("text", "heading"):
            assert w["archetype"]["id"]
    # the generated format must be saveable as-is
    saved = sf_designer.post("/api/formats", json=fmt)
    assert saved.status_code == 200, saved.text


@pytest.mark.llm
@pytest.mark.snowflake
def test_run_narrative_with_llm(sf_designer):
    from app.seed import client_quarterly_review

    fid = sf_designer.post("/api/formats", json=client_quarterly_review().model_dump(mode="json")).json()["id"]
    run = sf_designer.post(
        "/api/runs",
        json={"format_id": fid, "values": {"client": "Euro Shopping Channel", "period": {"start": "2004-01-01", "end": "2004-12-31"}}},
    ).json()
    meta = run["snapshot"]["data"]["summary"]["meta"]
    assert meta["source"] == "llm", meta
    assert len(meta["text"]) > 50 and "<think>" not in meta["text"]
