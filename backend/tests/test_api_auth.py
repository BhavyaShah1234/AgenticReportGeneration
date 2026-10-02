import uuid

from tests.conftest import new_client, signup


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_signup_me_logout_login(client):
    domain = f"auth-{uuid.uuid4().hex[:6]}.example"
    me = signup(client, domain=domain, email=f"alice@{domain}")
    assert me["role"] == "designer"
    assert me["company"]["domain"] == domain
    assert me["snowflake_connected"] is False
    assert "session" in client.cookies

    r = client.get("/api/auth/me")
    assert r.status_code == 200 and r.json()["email"] == f"alice@{domain}"

    assert client.post("/api/auth/logout").json() == {"ok": True}
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401

    bad = client.post("/api/auth/login", json={"email": f"alice@{domain}", "password": "wrong-pass"})
    assert bad.status_code == 401 and "detail" in bad.json()
    ok = client.post("/api/auth/login", json={"email": f"ALICE@{domain}", "password": "secret123"})
    assert ok.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_same_domain_joins_company_and_duplicate_email():
    domain = f"join-{uuid.uuid4().hex[:6]}.example"
    a, b = new_client(), new_client()
    me_a = signup(a, domain=domain, email=f"a@{domain}")
    me_b = signup(b, domain=domain, role="viewer", email=f"b@{domain}")
    assert me_a["company"]["id"] == me_b["company"]["id"]
    assert me_b["role"] == "viewer"
    dup = new_client().post(
        "/api/auth/signup",
        json={"company_name": "X", "full_name": "X", "email": f"a@{domain}", "password": "secret123", "role": "designer"},
    )
    assert dup.status_code == 409


def test_unauthenticated_routes_401(client):
    for path in ("/api/formats", "/api/runs", "/api/connection", "/api/archetypes"):
        assert client.get(path).status_code == 401, path


def test_print_token_rejected(client):
    r = client.get("/api/print/runs/nope?token=garbage")
    assert r.status_code == 401
