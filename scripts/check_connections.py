"""Decrypt every stored Snowflake connection with the app secret and test it.

    env -u PYTHONPATH backend/.venv/bin/python scripts/check_connections.py

Prints company, role and OK/error only; never prints tokens.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlmodel import Session, select  # noqa: E402

from app.db import engine  # noqa: E402
from app.models import Company, SnowflakeConnection  # noqa: E402
from app.snowflake.client import SnowflakeClient, SnowflakeCredentials  # noqa: E402
from app.snowflake.service import decrypt_token  # noqa: E402

with Session(engine) as s:
    for conn in s.exec(select(SnowflakeConnection)).all():
        company = s.get(Company, conn.company_id)
        try:
            client = SnowflakeClient(
                SnowflakeCredentials(conn.account, conn.user, decrypt_token(conn.token_encrypted), conn.warehouse, conn.role)
            )
            info = client.test()
            client.close()
            print(f"OK    {company.domain:<24} role={info['ROLE_NAME']}")
        except Exception as exc:
            print(f"FAIL  {company.domain:<24} {type(exc).__name__}: {str(exc)[:120]}")
