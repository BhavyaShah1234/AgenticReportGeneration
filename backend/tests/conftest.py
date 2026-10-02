"""Shared fixtures. The app DB and storage go to a temp dir; Snowflake creds come from env / ~/.bashrc."""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="arg-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ.setdefault("FRONTEND_URL", "http://127.0.0.1:9")  # unreachable: PDF step fails fast
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key")

from app.envutil import load_snowflake_env_from_bashrc  # noqa: E402

load_snowflake_env_from_bashrc()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

HAS_SNOWFLAKE = all(os.environ.get(k) for k in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_API"))


def pytest_collection_modifyitems(config, items):
    if HAS_SNOWFLAKE:
        return
    skip = pytest.mark.skip(reason="Snowflake credentials not available")
    for item in items:
        if "snowflake" in item.keywords:
            item.add_marker(skip)


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)


def new_client() -> TestClient:
    return TestClient(app)


def signup(client: TestClient, domain: str | None = None, role: str = "designer", email: str | None = None) -> dict:
    domain = domain or f"co-{uuid.uuid4().hex[:8]}.example"
    email = email or f"{role}-{uuid.uuid4().hex[:6]}@{domain}"
    r = client.post(
        "/api/auth/signup",
        json={"company_name": f"Company {domain}", "full_name": f"Test {role}", "email": email, "password": "secret123", "role": role},
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session", autouse=True)
def _app_lifespan():
    with TestClient(app):
        yield


@pytest.fixture
def client() -> TestClient:
    return new_client()


@pytest.fixture
def designer(client) -> TestClient:
    signup(client)
    return client


def snowflake_body() -> dict:
    return {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "token": os.environ["SNOWFLAKE_API"],
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE"),
        "role": os.environ.get("SNOWFLAKE_ROLE"),
        "default_table": "DEMO_CORP.SALES.V_SALES",
    }


@pytest.fixture(scope="session")
def sf_domain() -> str:
    return f"sf-{uuid.uuid4().hex[:8]}.example"


@pytest.fixture(scope="session")
def sf_designer(sf_domain) -> TestClient:
    """A designer whose company is connected to the live Snowflake account (session-scoped)."""
    if not HAS_SNOWFLAKE:
        pytest.skip("Snowflake credentials not available")
    c = new_client()
    signup(c, domain=sf_domain, email=f"designer@{sf_domain}")
    r = c.put("/api/connection", json=snowflake_body())
    assert r.status_code == 200, r.text
    return c
