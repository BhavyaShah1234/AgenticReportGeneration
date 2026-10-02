"""Create a least-privilege, read-only Snowflake role for the public demo (idempotent).

The hosted demo runs every query as DEMO_READER, which can only SELECT from
DEMO_CORP.SALES and use the warehouse, so the public app never runs as ACCOUNTADMIN.

    env -u PYTHONPATH backend/.venv/bin/python scripts/snowflake_demo_role.py

Undo with: DROP ROLE DEMO_READER;
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.envutil import snowflake_env  # noqa: E402
from app.snowflake.client import SnowflakeClient, SnowflakeCredentials  # noqa: E402

ROLE = "DEMO_READER"


def main() -> None:
    env = snowflake_env()
    admin = SnowflakeClient(
        SnowflakeCredentials(env["account"], env["user"], env["token"], env["warehouse"], "ACCOUNTADMIN")
    )
    wh = env["warehouse"] or "COMPUTE_WH"
    statements = [
        f"CREATE ROLE IF NOT EXISTS {ROLE} COMMENT = 'Read-only role for the public hackathon demo'",
        f"GRANT USAGE ON WAREHOUSE {wh} TO ROLE {ROLE}",
        f"GRANT USAGE ON DATABASE DEMO_CORP TO ROLE {ROLE}",
        f"GRANT USAGE ON SCHEMA DEMO_CORP.SALES TO ROLE {ROLE}",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA DEMO_CORP.SALES TO ROLE {ROLE}",
        f"GRANT SELECT ON ALL VIEWS IN SCHEMA DEMO_CORP.SALES TO ROLE {ROLE}",
        f'GRANT ROLE {ROLE} TO USER "{env["user"]}"',
    ]
    with admin.conn.cursor() as cur:
        for sql in statements:
            cur.execute(sql)
            print("ok:", sql.split(" TO ")[0][:70])
    admin.close()

    reader = SnowflakeClient(SnowflakeCredentials(env["account"], env["user"], env["token"], wh, ROLE))
    print("as", ROLE, "->", reader.test()["ROLE_NAME"])
    print("rows visible:", int(reader.query("SELECT COUNT(*) AS N FROM DEMO_CORP.SALES.V_SALES").iloc[0, 0]))
    try:
        reader.query("CREATE DATABASE SHOULD_NOT_WORK")
        print("WARNING: DEMO_READER could create a database")
    except Exception as exc:  # expected: insufficient privileges
        print("write blocked (expected):", type(exc).__name__)
    reader.close()


if __name__ == "__main__":
    main()
