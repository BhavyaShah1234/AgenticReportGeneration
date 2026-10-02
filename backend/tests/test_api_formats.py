import uuid

from tests.conftest import new_client, signup

BODY = {
    "name": "Test Format",
    "description": "d",
    "params": [{"name": "client", "label": "Client", "type": "client", "column": "CLIENT_NAME"}],
    "widgets": [
        {"id": "h", "type": "heading", "title": "Hello", "options": {"text": "Hello"}},
        {
            "id": "w1",
            "type": "line",
            "title": "Monthly sales",
            "archetype": {"id": "time_series", "params": {"date_column": "ORDER_DATE", "measure": "SALES"}},
        },
    ],
}


def test_format_crud_and_roles():
    domain = f"fmt-{uuid.uuid4().hex[:6]}.example"
    designer, viewer = new_client(), new_client()
    signup(designer, domain=domain)
    signup(viewer, domain=domain, role="viewer")

    r = designer.post("/api/formats", json=BODY)
    assert r.status_code == 200, r.text
    fmt = r.json()
    assert fmt["version"] == 1 and fmt["widgets"][1]["layout"]["w"] == 6

    # viewer can read but not write
    assert viewer.get(f"/api/formats/{fmt['id']}").status_code == 200
    assert [f["id"] for f in viewer.get("/api/formats").json()] == [fmt["id"]]
    assert viewer.post("/api/formats", json=BODY).status_code == 403
    assert viewer.delete(f"/api/formats/{fmt['id']}").status_code == 403

    upd = designer.put(f"/api/formats/{fmt['id']}", json={**BODY, "name": "Renamed"}).json()
    assert upd["version"] == 2 and upd["name"] == "Renamed"

    dup = designer.post(f"/api/formats/{fmt['id']}/duplicate").json()
    assert dup["id"] != fmt["id"] and dup["name"] == "Renamed (copy)" and dup["version"] == 1

    # another company can't see it
    other = new_client()
    signup(other)
    assert other.get(f"/api/formats/{fmt['id']}").status_code == 404
    assert other.get("/api/formats").json() == []

    assert designer.delete(f"/api/formats/{fmt['id']}").json() == {"ok": True}
    assert designer.get(f"/api/formats/{fmt['id']}").status_code == 404


def test_format_validation(designer):
    dup_ids = {**BODY, "widgets": [BODY["widgets"][0], BODY["widgets"][0]]}
    assert designer.post("/api/formats", json=dup_ids).status_code == 400
    assert designer.post("/api/formats", json={"widgets": []}).status_code == 422
