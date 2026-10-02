import pytest

from app.agent import service as agent_service
from app.agent.llm import LLMError
from app.auth.security import create_print_token
from app.seed import client_quarterly_review, product_line_performance

VALUES = {"client": "Euro Shopping Channel", "period": {"start": "2004-01-01", "end": "2004-12-31"}}


class _FailingLLM:
    model = "stub"
    base_url = "stub"

    async def chat(self, *a, **k):
        raise LLMError("LLM down (stub)")


@pytest.fixture(scope="module")
def formats(sf_designer):
    out = {}
    for body in (client_quarterly_review(), product_line_performance()):
        r = sf_designer.post("/api/formats", json=body.model_dump(mode="json"))
        assert r.status_code == 200, r.text
        out[body.name] = r.json()
    return out


@pytest.mark.snowflake
def test_run_requires_params(sf_designer, formats):
    fid = formats["Client Quarterly Review"]["id"]
    r = sf_designer.post("/api/runs", json={"format_id": fid, "values": {}})
    assert r.status_code == 400 and "Client" in r.json()["detail"]
    bad = sf_designer.post("/api/runs", json={"format_id": fid, "values": {"client": "X", "period": {"start": "bad"}}})
    assert bad.status_code == 400
    assert sf_designer.post("/api/runs", json={"format_id": "nope", "values": {}}).status_code == 404


@pytest.mark.snowflake
def test_client_quarterly_review_run(sf_designer, formats, monkeypatch):
    monkeypatch.setattr(agent_service, "get_llm", lambda *a, **k: _FailingLLM())
    fid = formats["Client Quarterly Review"]["id"]
    r = sf_designer.post("/api/runs", json={"format_id": fid, "values": VALUES})
    assert r.status_code == 200, r.text
    run = r.json()
    snap = run["snapshot"]
    assert snap is not None
    assert snap["company_name"].startswith("Company")
    assert snap["values"]["period"] == {"start": "2004-01-01", "end": "2004-12-31"}
    data = snap["data"]
    assert set(data) == {w["id"] for w in snap["format"]["widgets"]}
    errors = {k: v["error"] for k, v in data.items() if v["error"]}
    assert not errors, errors
    assert data["kpi_sales"]["rows"] and data["monthly_sales"]["rows"]
    assert 0 < len(data["top_products"]["rows"]) <= 10
    # narrative falls back deterministically when the LLM is down
    assert data["summary"]["meta"]["source"] == "fallback"
    assert "Euro Shopping Channel" in data["summary"]["meta"]["text"]

    # Frontend isn't running in tests: PDF fails with a clear error, snapshot is kept.
    assert run["status"] == "failed"
    assert "PDF rendering failed" in run["error"]
    assert run["pdf_url"] is None

    listed = sf_designer.get("/api/runs").json()
    assert listed[0]["id"] == run["id"] and listed[0]["created_by_name"] == "Test designer"
    assert sf_designer.get(f"/api/runs/{run['id']}").json()["snapshot"]["data"]["kpi_sales"]["rows"]
    assert sf_designer.get(f"/api/runs/{run['id']}/pdf").status_code == 404

    # print endpoint authenticates by token only
    from tests.conftest import new_client

    anon = new_client()
    tok = create_print_token(run["id"])
    p = anon.get(f"/api/print/runs/{run['id']}", params={"token": tok})
    assert p.status_code == 200 and p.json()["snapshot"]["format"]["name"] == "Client Quarterly Review"
    assert anon.get(f"/api/print/runs/{run['id']}", params={"token": create_print_token("other")}).status_code == 401


@pytest.mark.snowflake
def test_product_line_performance_run(sf_designer, formats, monkeypatch):
    monkeypatch.setattr(agent_service, "get_llm", lambda *a, **k: _FailingLLM())
    fid = formats["Product Line Performance"]["id"]
    run = sf_designer.post("/api/runs", json={"format_id": fid, "values": {"period": VALUES["period"]}}).json()
    errors = {k: v["error"] for k, v in run["snapshot"]["data"].items() if v["error"]}
    assert not errors, errors


@pytest.mark.snowflake
def test_pdf_download_filename(sf_designer, formats, monkeypatch, tmp_path):
    """Simulate a successful render to check the download headers."""
    import app.runs.service as run_service

    async def fake_render(run_id):
        p = tmp_path / f"{run_id}.pdf"
        p.write_bytes(b"%PDF-1.4\n%%EOF\n")
        return p

    monkeypatch.setattr(agent_service, "get_llm", lambda *a, **k: _FailingLLM())
    monkeypatch.setattr(run_service, "render_run_pdf", fake_render)
    fid = formats["Client Quarterly Review"]["id"]
    run = sf_designer.post("/api/runs", json={"format_id": fid, "values": VALUES}).json()
    assert run["status"] == "completed" and run["pdf_url"] == f"/api/runs/{run['id']}/pdf"
    r = sf_designer.get(run["pdf_url"], params={"download": 1})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    cd = r.headers["content-disposition"]
    assert cd.startswith("attachment") and "Client_Quarterly_Review-Euro_Shopping_Channel-" in cd
    inline = sf_designer.get(run["pdf_url"])
    assert inline.headers["content-disposition"].startswith("inline")
