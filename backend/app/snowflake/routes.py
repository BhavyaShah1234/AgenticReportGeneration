"""Snowflake connection + schema introspection routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session

from app.auth.deps import current_user, require_designer
from app.db import get_session
from app.models import SnowflakeConnection, User, utcnow
from app.schemas.api import ConnectionIn, ConnectionOut, ConnectionTestOut, TableOut
from app.snowflake import service
from app.snowflake.client import SnowflakeClient, SnowflakeCredentials

router = APIRouter(tags=["snowflake"])


def _err(e: Exception) -> str:
    msg = str(e).strip() or type(e).__name__
    return msg[:500]


def _http_error(e: Exception) -> HTTPException:
    if isinstance(e, service.NotConnected):
        return HTTPException(409, str(e))
    if isinstance(e, ValueError):
        return HTTPException(400, str(e))
    return HTTPException(502, f"Snowflake error: {_err(e)}")


# --- connection ---------------------------------------------------------------
@router.get("/connection", response_model=ConnectionOut)
def get_connection(user: User = Depends(current_user), session: Session = Depends(get_session)) -> ConnectionOut:
    conn = service.get_connection_row(user.company_id, session)
    if conn is None:
        return ConnectionOut(connected=False)
    return ConnectionOut(
        connected=True,
        account=conn.account,
        user=conn.user,
        warehouse=conn.warehouse,
        role=conn.role,
        default_table=conn.default_table,
        last_tested_at=conn.last_tested_at,
    )


def _test_creds(creds: SnowflakeCredentials) -> dict[str, str]:
    client = SnowflakeClient(creds)
    try:
        return client.test()
    finally:
        client.close()


@router.put("/connection", response_model=ConnectionTestOut)
async def put_connection(
    body: ConnectionIn, user: User = Depends(require_designer), session: Session = Depends(get_session)
) -> ConnectionTestOut:
    existing = service.get_connection_row(user.company_id, session)
    token = (body.token or "").strip()
    if not token:
        if existing is None:
            raise HTTPException(400, "token is required")
        token = service.decrypt_token(existing.token_encrypted)
    default_table = (body.default_table or "").strip() or None
    if default_table:
        try:
            default_table = service.qualified(default_table)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    creds = SnowflakeCredentials(
        account=body.account.strip(),
        user=body.user.strip(),
        token=token,
        warehouse=(body.warehouse or "").strip() or None,
        role=(body.role or "").strip() or None,
    )
    try:
        info = await run_in_threadpool(_test_creds, creds)
    except Exception as e:
        raise HTTPException(400, f"Connection test failed: {_err(e)}") from e

    conn = existing or SnowflakeConnection(company_id=user.company_id, account="", user="", token_encrypted="")
    conn.account, conn.user = creds.account, creds.user
    conn.warehouse, conn.role = creds.warehouse, creds.role
    conn.default_table = default_table
    conn.token_encrypted = service.encrypt_token(token)
    conn.last_tested_at = utcnow()
    conn.updated_at = utcnow()
    session.add(conn)
    session.commit()
    service.drop_client(user.company_id)
    return ConnectionTestOut(ok=True, info=info)


@router.post("/connection/test", response_model=ConnectionTestOut)
async def test_connection(user: User = Depends(current_user), session: Session = Depends(get_session)) -> ConnectionTestOut:
    conn = service.get_connection_row(user.company_id, session)
    if conn is None:
        return ConnectionTestOut(ok=False, error="Snowflake is not connected")
    try:
        client = await run_in_threadpool(service.get_client, user.company_id)
        info = await run_in_threadpool(client.test)
    except Exception as e:
        service.drop_client(user.company_id)
        return ConnectionTestOut(ok=False, error=_err(e))
    conn.last_tested_at = utcnow()
    session.add(conn)
    session.commit()
    return ConnectionTestOut(ok=True, info=info)


# --- schema -----------------------------------------------------------------
@router.get("/schema/tables", response_model=list[TableOut])
async def schema_tables(user: User = Depends(current_user)) -> list[dict[str, str]]:
    try:
        return await run_in_threadpool(service.list_tables, user.company_id)
    except Exception as e:
        raise _http_error(e) from e


@router.get("/schema/columns")
async def schema_columns(table: str = Query(...), user: User = Depends(current_user)) -> list[dict[str, str]]:
    try:
        cols = await run_in_threadpool(service.list_columns, user.company_id, table)
    except Exception as e:
        raise _http_error(e) from e
    if not cols:
        raise HTTPException(404, f"Table {table} not found or has no columns")
    return cols


@router.get("/schema/values")
async def schema_values(
    table: str = Query(...),
    column: str = Query(...),
    q: str | None = Query(default=None),
    user: User = Depends(current_user),
) -> list[Any]:
    try:
        return await run_in_threadpool(service.distinct_values, user.company_id, table, column, q)
    except Exception as e:
        raise _http_error(e) from e
