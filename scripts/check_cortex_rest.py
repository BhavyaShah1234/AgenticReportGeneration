"""Try the Cortex REST API the ways Snowflake-Labs/cortex-rest-api-demo does it:
plain Bearer PAT (README curl), Bearer PAT + token-type header, and a connector session
token (`Snowflake Token="..."`, as in its streamlit.py). Prints status codes only.

    env -u PYTHONPATH backend/.venv/bin/python scripts/check_cortex_rest.py
"""

from __future__ import annotations

import os
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.envutil import snowflake_env  # noqa: E402
from app.snowflake.client import SnowflakeClient, SnowflakeCredentials  # noqa: E402

env = snowflake_env()
host = f"{env['account'].lower()}.snowflakecomputing.com"
body = {"model": "llama3.1-70b", "messages": [{"role": "user", "content": "Write me a one line poem about Snowflake"}],
        "stream": False}

sf = SnowflakeClient(SnowflakeCredentials(env["account"], env["user"], env["token"], env["warehouse"], env["role"]))
session_token = sf.conn.rest.token

variants = {
    "Bearer PAT (README curl)": {"Authorization": f"Bearer {env['token']}"},
    "Bearer PAT + token-type": {"Authorization": f"Bearer {env['token']}",
                                "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN"},
    "Session token (streamlit.py)": {"Authorization": f'Snowflake Token="{session_token}"'},
}
for path in ("/api/v2/cortex/inference:complete", "/api/v2/cortex/v1/chat/completions"):
    for name, headers in variants.items():
        r = httpx.post(f"https://{host}{path}", json=body, timeout=60,
                       headers={"Content-Type": "application/json", "Accept": "application/json", **headers})
        print(f"{path:<38} {name:<30} HTTP {r.status_code}  {r.text[:110]!r}")
sf.close()
