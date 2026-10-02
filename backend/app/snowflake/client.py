"""Thin Snowflake access layer shared by the API, archetypes and tests.

All SQL runs through `SnowflakeClient.query`, which uses pyformat binding (`%(name)s`)
so user/runtime values are never string-concatenated into SQL.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import pandas as pd
import snowflake.connector
from snowflake.connector import SnowflakeConnection

from app.config import get_settings


@dataclass(frozen=True)
class SnowflakeCredentials:
    account: str
    user: str
    token: str  # Programmatic Access Token
    warehouse: str | None = None
    role: str | None = None
    database: str | None = None
    schema: str | None = None

    @classmethod
    def from_settings(cls) -> SnowflakeCredentials:
        s = get_settings()
        if not (s.snowflake_account and s.snowflake_user and s.snowflake_api):
            raise RuntimeError("SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER / SNOWFLAKE_API are not set")
        return cls(s.snowflake_account, s.snowflake_user, s.snowflake_api, s.snowflake_warehouse, s.snowflake_role)


class SnowflakeClient:
    def __init__(self, creds: SnowflakeCredentials):
        self.creds = creds
        self._conn: SnowflakeConnection | None = None
        self._lock = threading.Lock()

    def _connect(self) -> SnowflakeConnection:
        c = self.creds
        return snowflake.connector.connect(
            account=c.account,
            user=c.user,
            authenticator="PROGRAMMATIC_ACCESS_TOKEN",
            token=c.token,
            warehouse=c.warehouse,
            role=c.role,
            database=c.database,
            schema=c.schema,
            login_timeout=30,
            network_timeout=get_settings().query_timeout_s,
            session_parameters={
                "STATEMENT_TIMEOUT_IN_SECONDS": get_settings().query_timeout_s,
                "QUERY_TAG": "agentic-report-gen",
            },
        )

    @property
    def conn(self) -> SnowflakeConnection:
        with self._lock:
            if self._conn is None or self._conn.is_closed():
                self._conn = self._connect()
            return self._conn

    def query(self, sql: str, params: dict[str, Any] | None = None, max_rows: int | None = None) -> pd.DataFrame:
        """Run a read query and return a DataFrame with UPPERCASE column names."""
        limit = max_rows or get_settings().max_rows
        with self.conn.cursor() as cur:
            cur.execute(sql, params or {})
            rows = cur.fetchmany(limit)
            cols = [d.name for d in cur.description]
        return pd.DataFrame.from_records(rows, columns=cols)

    def test(self) -> dict[str, str]:
        df = self.query(
            "SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS ACCOUNT, "
            "CURRENT_USER() AS USER_NAME, CURRENT_ROLE() AS ROLE_NAME, "
            "CURRENT_WAREHOUSE() AS WAREHOUSE, CURRENT_VERSION() AS VERSION"
        )
        return {k: str(v) for k, v in df.iloc[0].to_dict().items()}

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
