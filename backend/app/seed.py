"""Seed demo data (idempotent): `python -m app.seed`.

Creates company "Classic Models Inc." (classicmodels.com), users designer@/viewer@classicmodels.com
(password demo1234), the Snowflake connection from env / ~/.bashrc, and two demo formats.
"""

from __future__ import annotations

from app.envutil import snowflake_env

snowflake_env()  # populate os.environ before settings are read

from sqlmodel import Session, select  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from app.models import Company, ReportFormatRow, SnowflakeConnection, User, utcnow  # noqa: E402
from app.schemas.report import ReportFormatBody  # noqa: E402
from app.snowflake.service import encrypt_token  # noqa: E402

TABLE = "DEMO_CORP.SALES.V_SALES"
DOMAIN = "classicmodels.com"
PASSWORD = "demo1234"


def _w(id, type, title, x, y, w, h, archetype=None, params=None, fmt="number", **opts):
    spec = {"id": id, "type": type, "title": title, "layout": {"x": x, "y": y, "w": w, "h": h}, "options": {"format": fmt, **opts}}
    if archetype:
        spec["archetype"] = {"id": archetype, "params": params or {}}
        spec["source"] = {"table": TABLE}
    return spec


def client_quarterly_review() -> ReportFormatBody:
    return ReportFormatBody.model_validate(
        {
            "name": "Client Quarterly Review",
            "description": "Account review for one client over a chosen period: headline KPIs, trend, mix and top products.",
            "default_source": {"table": TABLE},
            "params": [
                {"name": "client", "label": "Client", "type": "client", "column": "CLIENT_NAME"},
                {"name": "period", "label": "Period", "type": "date_range", "column": "ORDER_DATE",
                 "default": {"start": "2004-01-01", "end": "2004-12-31"}},
            ],
            "widgets": [
                _w("summary", "text", "Executive summary", 0, 0, 12, 5, narrative=True,
                   text="Summarize this client's sales performance, trend and product mix for the period."),
                _w("kpi_sales", "kpi", "Total sales", 0, 5, 6, 4, "kpi_summary",
                   {"measure": "SALES", "agg": "sum", "date_column": "ORDER_DATE", "compare": "previous_period"}, fmt="currency"),
                _w("kpi_orders", "kpi", "Orders", 6, 5, 6, 4, "kpi_summary",
                   {"measure": "ORDER_NUMBER", "agg": "count_distinct", "date_column": "ORDER_DATE", "compare": "previous_period"}),
                _w("monthly_sales", "line", "Monthly sales", 0, 9, 12, 7, "time_series",
                   {"date_column": "ORDER_DATE", "measure": "SALES", "agg": "sum", "grain": "month", "cumulative": False}, fmt="currency"),
                _w("by_product_line", "bar", "Sales by product line", 0, 16, 6, 7, "aggregate",
                   {"dimensions": ["PRODUCT_LINE"], "measure": "SALES", "agg": "sum", "sort": "desc"}, fmt="currency",
                   extra={"horizontal": True}),
                _w("deal_size", "pie", "Deal size share", 6, 16, 6, 7, "share_of_total",
                   {"dimension": "DEAL_SIZE", "measure": "SALES", "agg": "sum", "top_k": 6}, fmt="currency"),
                _w("top_products", "table", "Top products", 0, 23, 12, 8, "top_n",
                   {"dimension": "PRODUCT_CODE", "measure": "SALES", "agg": "sum", "n": 10, "include_other": False}, fmt="currency"),
            ],
        }
    )


def product_line_performance() -> ReportFormatBody:
    return ReportFormatBody.model_validate(
        {
            "name": "Product Line Performance",
            "description": "Portfolio view across all clients: product line growth, top clients, yearly mix and smoothed trend.",
            "default_source": {"table": TABLE},
            "params": [
                {"name": "period", "label": "Period", "type": "date_range", "column": "ORDER_DATE",
                 "default": {"start": "2004-01-01", "end": "2004-12-31"}},
            ],
            "widgets": [
                _w("pop_product_line", "bar", "Sales by product line vs previous period", 0, 0, 12, 8, "period_over_period",
                   {"date_column": "ORDER_DATE", "measure": "SALES", "agg": "sum", "grain": "quarter", "dimension": "PRODUCT_LINE"},
                   fmt="currency"),
                _w("top_clients", "bar", "Top 10 clients", 0, 8, 6, 8, "top_n",
                   {"dimension": "CLIENT_NAME", "measure": "SALES", "agg": "sum", "n": 10, "include_other": False}, fmt="currency",
                   extra={"horizontal": True}),
                _w("moving_avg", "line", "Monthly sales (3-month moving average)", 6, 8, 6, 8, "moving_average",
                   {"date_column": "ORDER_DATE", "measure": "SALES", "agg": "sum", "grain": "month", "window": 3}, fmt="currency"),
                _w("pivot_line_year", "table", "Sales by product line and year", 0, 16, 12, 7, "pivot",
                   {"row_dimension": "PRODUCT_LINE", "column_dimension": "YEAR", "measure": "SALES", "agg": "sum", "max_columns": 12},
                   fmt="currency"),
            ],
        }
    )


def seed() -> dict:
    init_db()
    out: dict = {}
    with Session(engine) as s:
        company = s.exec(select(Company).where(Company.domain == DOMAIN)).first()
        if company is None:
            company = Company(name="Classic Models Inc.", domain=DOMAIN)
            s.add(company)
            s.flush()
        out["company_id"] = company.id

        users = {}
        for email, name, role in (
            (f"designer@{DOMAIN}", "Dana Designer", "designer"),
            (f"viewer@{DOMAIN}", "Victor Viewer", "viewer"),
        ):
            u = s.exec(select(User).where(User.email == email)).first()
            if u is None:
                u = User(company_id=company.id, email=email, full_name=name, password_hash=hash_password(PASSWORD), role=role)
                s.add(u)
                s.flush()
            users[role] = u

        out.update(provision_demo_content(s, company.id, users["designer"].id))

        if get_settings().demo_mode:
            # In the public demo every company uses the server's demo connection (see signup), so a
            # change of Snowflake account/token is applied to all of them, not just Classic Models.
            env = snowflake_env()
            others = s.exec(select(SnowflakeConnection).where(SnowflakeConnection.company_id != company.id)).all()
            for conn in others:
                conn.account, conn.user = env["account"], env["user"]
                conn.warehouse, conn.role = env["warehouse"], env["role"]
                conn.token_encrypted = encrypt_token(env["token"])
                conn.updated_at = utcnow()
                s.add(conn)
            out["demo_connections_refreshed"] = len(others)
        s.commit()
    return out


def provision_demo_content(s: Session, company_id: str, created_by: str) -> dict:
    """Give a company the server's demo Snowflake connection and the demo formats (idempotent).

    Used by the seed and, in DEMO_MODE, by signup for every newly created company.
    """
    out: dict = {}
    env = snowflake_env()
    if env["account"] and env["user"] and env["token"]:
        conn = s.exec(select(SnowflakeConnection).where(SnowflakeConnection.company_id == company_id)).first()
        if conn is None:
            conn = SnowflakeConnection(company_id=company_id, account="", user="", token_encrypted="")
        conn.account, conn.user = env["account"], env["user"]
        conn.warehouse, conn.role = env["warehouse"], env["role"]
        conn.default_table = TABLE
        conn.token_encrypted = encrypt_token(env["token"])
        conn.updated_at = utcnow()
        s.add(conn)
        out["snowflake"] = f"configured (role {env['role']})"
    else:
        out["snowflake"] = "skipped (SNOWFLAKE_ACCOUNT/USER/API not set)"

    out["formats"] = {}
    for body in (client_quarterly_review(), product_line_performance()):
        row = s.exec(
            select(ReportFormatRow).where(ReportFormatRow.company_id == company_id, ReportFormatRow.name == body.name)
        ).first()
        if row is None:
            row = ReportFormatRow(company_id=company_id, created_by=created_by, name=body.name, body_json=body.model_dump_json())
        elif row.body_json != body.model_dump_json():
            row.body_json = body.model_dump_json()
            row.version += 1
            row.updated_at = utcnow()
        s.add(row)
        s.flush()
        out["formats"][body.name] = row.id
    return out


if __name__ == "__main__":
    result = seed()
    print(f"Seeded company {result['company_id']} (Classic Models Inc.)")
    print(f"  users: designer@{DOMAIN} / viewer@{DOMAIN}  password: {PASSWORD}")
    print(f"  snowflake: {result['snowflake']}")
    if "demo_connections_refreshed" in result:
        print(f"  demo mode: refreshed {result['demo_connections_refreshed']} other company connection(s)")
    for name, fid in result["formats"].items():
        print(f"  format: {name} -> {fid}")
