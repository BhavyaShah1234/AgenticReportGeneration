"""Probe Snowflake Cortex: which open-weight models answer, via SQL and via the
OpenAI-compatible REST API. Prints model availability only, never tokens.

    env -u PYTHONPATH backend/.venv/bin/python scripts/check_cortex.py [ROLE]
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from openai import AsyncOpenAI  # noqa: E402

from app.envutil import snowflake_env  # noqa: E402
from app.snowflake.client import SnowflakeClient, SnowflakeCredentials  # noqa: E402

MODELS = ["llama3.1-8b", "llama3.1-70b", "llama3.3-70b", "snowflake-llama-3.3-70b", "llama4-maverick",
          "mistral-large2", "mistral-7b", "mixtral-8x7b", "deepseek-r1"]


def sql_probe(env: dict, role: str) -> None:
    c = SnowflakeClient(SnowflakeCredentials(env["account"], env["user"], env["token"], env["warehouse"], role))
    print("== SQL: SNOWFLAKE.CORTEX.COMPLETE ==")
    print("  cross-region:", c.query("SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION' IN ACCOUNT").iloc[0]["value"])
    for m in MODELS:
        t = time.time()
        try:
            out = c.query("SELECT SNOWFLAKE.CORTEX.COMPLETE(%(m)s, 'Reply with the single word OK') AS R", {"m": m}).iloc[0, 0]
            print(f"  OK   {m:<26} {time.time() - t:4.1f}s  {str(out).strip()[:30]!r}")
        except Exception as e:
            print(f"  FAIL {m:<26} {str(e).splitlines()[0][:110]}")
    c.close()


async def rest_probe(env: dict) -> None:
    base = f"https://{env['account'].lower()}.snowflakecomputing.com/api/v2/cortex/v1"
    client = AsyncOpenAI(base_url=base, api_key=env["token"], max_retries=0, timeout=90)
    print("== REST (OpenAI-compatible):", base.replace(env["account"].lower(), "<account>"))
    for m in ("llama3.1-8b", "llama3.3-70b", "mistral-large2"):
        t = time.time()
        try:
            r = await client.chat.completions.create(model=m, messages=[{"role": "user", "content": "Reply with OK"}], max_tokens=10)
            print(f"  chat OK   {m:<16} {time.time() - t:4.1f}s {r.choices[0].message.content!r}")
        except Exception as e:
            print(f"  chat FAIL {m:<16} {type(e).__name__}: {str(e)[:160]}")
            continue
        schema = {"type": "object", "properties": {"color": {"type": "string"}, "n": {"type": "integer"}},
                  "required": ["color", "n"], "additionalProperties": False}
        try:
            r = await client.chat.completions.create(
                model=m, messages=[{"role": "user", "content": "Give a color and a number as JSON."}], max_tokens=60,
                response_format={"type": "json_schema", "json_schema": {"name": "x", "schema": schema}})
            print(f"  json_schema OK   {m:<16} {r.choices[0].message.content!r}")
        except Exception as e:
            print(f"  json_schema FAIL {m:<16} {type(e).__name__}: {str(e)[:160]}")


if __name__ == "__main__":
    env = snowflake_env()
    sql_probe(env, sys.argv[1] if len(sys.argv) > 1 else env["role"])
    asyncio.run(rest_probe(env))
