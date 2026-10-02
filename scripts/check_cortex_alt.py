"""Probe alternative Cortex entry points (AI_COMPLETE SQL, inference:complete REST)."""

from __future__ import annotations

import os
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.envutil import snowflake_env  # noqa: E402
from app.snowflake.client import SnowflakeClient, SnowflakeCredentials  # noqa: E402

env = snowflake_env()
c = SnowflakeClient(SnowflakeCredentials(env["account"], env["user"], env["token"], env["warehouse"], env["role"]))
try:
    print("AI_COMPLETE:", c.query("SELECT AI_COMPLETE('llama3.1-8b', 'Reply OK') AS R").iloc[0, 0])
except Exception as e:
    print("AI_COMPLETE FAIL:", str(e).splitlines()[0][:140])
c.close()

url = f"https://{env['account'].lower()}.snowflakecomputing.com/api/v2/cortex/inference:complete"
r = httpx.post(
    url,
    headers={"Authorization": f"Bearer {env['token']}", "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
             "Content-Type": "application/json", "Accept": "application/json"},
    json={"model": "llama3.1-8b", "messages": [{"role": "user", "content": "Reply OK"}], "max_tokens": 10, "stream": False},
    timeout=60,
)
print("inference:complete HTTP", r.status_code, r.text[:200])
