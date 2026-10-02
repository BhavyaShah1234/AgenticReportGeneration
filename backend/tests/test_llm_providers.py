"""LLM provider selection: Snowflake Cortex (open-weight models) with Ollama fallback."""

from __future__ import annotations

import asyncio
import os

import pytest
from sqlmodel import Session, select

from app.agent import llm as llm_mod
from app.agent.llm import FallbackLLM, LLMClient, LLMError, get_llm
from app.config import get_settings
from app.db import engine
from app.models import Company, SnowflakeConnection
from app.snowflake.service import encrypt_token
from tests.conftest import new_client, signup


@pytest.fixture
def cortex_mode(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "cortex")
    monkeypatch.setattr(get_settings(), "llm_fallback", True)
    yield


def _company_with_connection(account: str = "MYORG-ACCT1", token: str = "pat-secret-value", user: str = "U") -> str:
    me = signup(new_client())
    with Session(engine) as s:
        s.add(SnowflakeConnection(company_id=me["company"]["id"], account=account, user=user, token_encrypted=encrypt_token(token)))
        s.commit()
    return me["company"]["id"]


def test_default_provider_is_openai_compatible():
    llm = get_llm("any-company")
    assert isinstance(llm, LLMClient) and llm.base_url == get_settings().llm_base_url


def test_cortex_uses_company_account_and_open_weight_model(cortex_mode):
    company_id = _company_with_connection()
    llm = get_llm(company_id)
    assert isinstance(llm, FallbackLLM)
    assert llm.primary.base_url == "https://myorg-acct1.snowflakecomputing.com/api/v2/cortex/v1"
    assert llm.primary.model == "llama3.1-70b" and llm.label == "cortex:llama3.1-70b"
    assert llm.primary.client.api_key == "pat-secret-value"
    assert llm.primary._caps["reasoning_effort"] is False
    assert llm.fallback.base_url == get_settings().llm_base_url


def test_cortex_without_connection_uses_default(cortex_mode):
    me = signup(new_client())
    assert isinstance(get_llm(me["company"]["id"]), LLMClient)


class _Fake:
    def __init__(self, label: str, fail: bool):
        self.label, self.fail = label, fail
        self.provider, self.model = label.split(":", 1)
        self.base_url = f"http://{self.provider}"

    async def chat(self, *a, **k):
        if self.fail:
            raise LLMError("403 not allowed")
        return f"answer from {self.label}"


def test_fallback_switches_provider_and_label():
    llm_mod._PRIMARY_DOWN.clear()
    f = FallbackLLM(_Fake("cortex:llama3.1-70b", fail=True), _Fake("ollama:qwen3:8b", fail=False))  # type: ignore[arg-type]
    assert asyncio.run(f.chat([])) == "answer from ollama:qwen3:8b"
    assert f.label == "ollama:qwen3:8b"

    # A failed primary is skipped (not re-called) until PRIMARY_RETRY_AFTER_S passes.
    recovered = FallbackLLM(_Fake("cortex:llama3.1-70b", fail=False), _Fake("ollama:qwen3:8b", fail=False))  # type: ignore[arg-type]
    assert asyncio.run(recovered.chat([])) == "answer from ollama:qwen3:8b"

    llm_mod._PRIMARY_DOWN.clear()
    ok = FallbackLLM(_Fake("cortex:llama3.1-70b", fail=False), _Fake("ollama:qwen3:8b", fail=False))  # type: ignore[arg-type]
    assert asyncio.run(ok.chat([])) == "answer from cortex:llama3.1-70b"
    assert ok.label == "cortex:llama3.1-70b"


def test_normalize_roles_for_cortex():
    msgs = [
        {"role": "system", "content": "A"},
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "bad"},
        {"role": "user", "content": "fix it"},
        {"role": "system", "content": "schema hint"},
    ]
    out = llm_mod.normalize_roles(msgs)
    assert [m["role"] for m in out] == ["system", "user", "assistant", "user"]
    assert out[0]["content"] == "A\n\nschema hint"
    assert llm_mod.normalize_roles([{"role": "user", "content": "a"}, {"role": "user", "content": "b"}]) == [
        {"role": "user", "content": "a\n\nb"}
    ]


@pytest.mark.snowflake
@pytest.mark.llm
def test_live_cortex_designs_widget(cortex_mode):
    """The real agent loop (schema prompt, structured output, validation) on Cortex, no fallback."""
    from app.agent import service as agent_service
    from app.envutil import snowflake_env

    if os.environ.get("EXPECT_CORTEX") != "1":
        pytest.skip("set EXPECT_CORTEX=1 to require a Cortex-enabled account")
    env = snowflake_env()
    company_id = _company_with_connection(env["account"], env["token"], env["user"])
    get_settings().llm_fallback = False
    try:
        widget, _ = asyncio.run(
            agent_service.design_widget(company_id, "monthly sales as a line chart", "DEMO_CORP.SALES.V_SALES", [], [])
        )
    finally:
        get_settings().llm_fallback = True
    assert widget.type in {"line", "area"} and widget.archetype and widget.archetype.id in {"time_series", "moving_average"}


@pytest.mark.snowflake
@pytest.mark.llm
def test_live_cortex_or_fallback(cortex_mode):
    """Against the real account: Cortex if the account allows it, otherwise the Ollama fallback."""
    from app.envutil import snowflake_env

    env = snowflake_env()
    company_id = _company_with_connection(env["account"], env["token"], env["user"])
    llm = get_llm(company_id)
    text = asyncio.run(llm.chat([{"role": "user", "content": "Reply with the single word OK."}], max_tokens=20))
    assert text.strip()
    print("answered by", llm.label)
    if os.environ.get("EXPECT_CORTEX") == "1":
        assert llm.label.startswith("cortex:"), "Cortex was expected to answer (EXPECT_CORTEX=1)"
