"""Load `export SNOWFLAKE_*=...` lines from ~/.bashrc into os.environ (non-interactive
shells skip them). Values are never printed or logged."""

from __future__ import annotations

import os
import re
import shlex

_PAT = re.compile(r"^\s*export\s+(SNOWFLAKE_[A-Z_]+)=(.*)$")


def load_snowflake_env_from_bashrc() -> None:
    rc = os.path.expanduser("~/.bashrc")
    if not os.path.exists(rc):
        return
    with open(rc) as fh:
        for line in fh:
            m = _PAT.match(line)
            if m and not os.environ.get(m.group(1)):
                try:
                    parts = shlex.split(m.group(2), comments=True)
                except ValueError:
                    continue
                os.environ[m.group(1)] = parts[0] if parts else ""


def snowflake_env() -> dict[str, str | None]:
    """Server-side Snowflake credentials.

    With DEMO_MODE=1 and a SNOWFLAKE_DEMO_API token (a PAT restricted to the read-only
    demo role), the public demo uses that token and SNOWFLAKE_DEMO_ROLE (default DEMO_READER)
    instead of the owner's admin token.
    """
    load_snowflake_env_from_bashrc()
    token = os.environ.get("SNOWFLAKE_API")
    role = os.environ.get("SNOWFLAKE_ROLE")
    if os.environ.get("DEMO_MODE", "").lower() in {"1", "true", "yes"} and os.environ.get("SNOWFLAKE_DEMO_API"):
        token = os.environ["SNOWFLAKE_DEMO_API"]
        role = os.environ.get("SNOWFLAKE_DEMO_ROLE") or "DEMO_READER"
    return {
        "account": os.environ.get("SNOWFLAKE_ACCOUNT"),
        "user": os.environ.get("SNOWFLAKE_USER"),
        "token": token,
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE"),
        "role": role,
    }
