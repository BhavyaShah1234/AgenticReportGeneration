"""DEMO_MODE: a brand-new company gets the demo Snowflake connection and demo formats."""

from __future__ import annotations

import pytest

from app.config import get_settings
from tests.conftest import HAS_SNOWFLAKE, new_client, signup


@pytest.fixture
def demo_mode(monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", True)
    yield


@pytest.mark.skipif(not HAS_SNOWFLAKE, reason="needs server-side Snowflake creds")
def test_signup_in_demo_mode_provisions_company(demo_mode):
    client = new_client()
    me = signup(client)
    assert me["snowflake_connected"] is True
    names = sorted(f["name"] for f in client.get("/api/formats").json())
    assert names == ["Client Quarterly Review", "Product Line Performance"]


def test_signup_without_demo_mode_is_empty():
    client = new_client()
    me = signup(client)
    assert me["snowflake_connected"] is False
    assert client.get("/api/formats").json() == []
