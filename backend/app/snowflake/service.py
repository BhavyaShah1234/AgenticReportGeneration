"""Per-company Snowflake access: encrypted token storage, client cache and schema introspection.

All functions here are blocking; call them from routes via `run_in_threadpool`.
"""

from __future__ import annotations

import base64
import hashlib
import re
import threading
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlmodel import Session, select

from app.config import get_settings
from app.db import engine
from app.models import SnowflakeConnection
from app.snowflake.client import SnowflakeClient, SnowflakeCredentials

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
SYSTEM_DBS_PREFIX = "SNOWFLAKE"
_SCHEMA_TTL_S = 300


class NotConnected(Exception):
    """The company has no Snowflake connection configured."""


# --- token encryption -----------------------------------------------------------
def _fernet() -> Fernet:
    key = hashlib.sha256(get_settings().app_secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(token_encrypted: str) -> str:
    try:
        return _fernet().decrypt(token_encrypted.encode()).decode()
    except InvalidToken as e:  # secret key changed
        raise NotConnected("Stored Snowflake token cannot be decrypted; reconnect Snowflake") from e


# --- identifiers ---------------------------------------------------------------
def validate_ident(part: str) -> str:
    if not IDENT_RE.match(part or ""):
        raise ValueError(f"Invalid identifier: {part!r}")
    return part.upper()


def parse_table(table: str) -> tuple[str, str, str]:
    parts = (table or "").split(".")
    if len(parts) != 3:
        raise ValueError("Table must be fully qualified as DB.SCHEMA.NAME")
    db, schema, name = (validate_ident(p) for p in parts)
    return db, schema, name


def qualified(table: str) -> str:
    return ".".join(parse_table(table))


# --- client cache ----------------------------------------------------------------
_clients: dict[str, tuple[str, SnowflakeClient]] = {}
_clients_lock = threading.Lock()


def credentials_for(conn: SnowflakeConnection) -> SnowflakeCredentials:
    return SnowflakeCredentials(
        account=conn.account,
        user=conn.user,
        token=decrypt_token(conn.token_encrypted),
        warehouse=conn.warehouse or None,
        role=conn.role or None,
    )


def _fingerprint(conn: SnowflakeConnection) -> str:
    raw = "|".join([conn.account, conn.user, conn.warehouse or "", conn.role or "", conn.token_encrypted])
    return hashlib.sha256(raw.encode()).hexdigest()


def get_connection_row(company_id: str, session: Session | None = None) -> SnowflakeConnection | None:
    def _q(s: Session) -> SnowflakeConnection | None:
        return s.exec(select(SnowflakeConnection).where(SnowflakeConnection.company_id == company_id)).first()

    if session is not None:
        return _q(session)
    with Session(engine) as s:
        return _q(s)


def get_client(company_id: str) -> SnowflakeClient:
    conn = get_connection_row(company_id)
    if conn is None:
        raise NotConnected("Snowflake is not connected for this company")
    fp = _fingerprint(conn)
    with _clients_lock:
        cached = _clients.get(company_id)
        if cached and cached[0] == fp:
            return cached[1]
        if cached:
            try:
                cached[1].close()
            except Exception:
                pass
        client = SnowflakeClient(credentials_for(conn))
        _clients[company_id] = (fp, client)
        _schema_cache_clear(company_id)
        return client


def drop_client(company_id: str) -> None:
    with _clients_lock:
        cached = _clients.pop(company_id, None)
    if cached:
        try:
            cached[1].close()
        except Exception:
            pass
    _schema_cache_clear(company_id)


def default_table(company_id: str) -> str:
    conn = get_connection_row(company_id)
    return (conn.default_table if conn and conn.default_table else None) or get_settings().snowflake_default_table


# --- schema introspection ---------------------------------------------------------
_schema_cache: dict[tuple, tuple[float, Any]] = {}
_schema_lock = threading.Lock()


def _schema_cache_clear(company_id: str) -> None:
    with _schema_lock:
        for k in [k for k in _schema_cache if k[0] == company_id]:
            del _schema_cache[k]


def _cached(key: tuple, fn):
    now = time.time()
    with _schema_lock:
        hit = _schema_cache.get(key)
        if hit and now - hit[0] < _SCHEMA_TTL_S:
            return hit[1]
    value = fn()
    with _schema_lock:
        _schema_cache[key] = (now, value)
    return value


def list_tables(company_id: str) -> list[dict[str, str]]:
    def _load() -> list[dict[str, str]]:
        client = get_client(company_id)
        df = client.query("SHOW TERSE OBJECTS IN ACCOUNT", max_rows=20000)
        cols = {c.lower(): c for c in df.columns}
        out = []
        for _, r in df.iterrows():
            kind = str(r[cols["kind"]]).upper()
            db, schema, name = str(r[cols["database_name"]]), str(r[cols["schema_name"]]), str(r[cols["name"]])
            if kind not in ("TABLE", "VIEW"):
                continue
            if db.upper().startswith(SYSTEM_DBS_PREFIX) or schema.upper() == "INFORMATION_SCHEMA":
                continue
            out.append({"table": f"{db}.{schema}.{name}", "kind": kind})
        out.sort(key=lambda t: (not t["table"].startswith("DEMO_CORP."), t["table"]))
        return out

    return _cached((company_id, "tables"), _load)


def map_type(sf_type: str) -> str:
    t = (sf_type or "").upper()
    if any(k in t for k in ("NUMBER", "DECIMAL", "NUMERIC", "INT", "FLOAT", "DOUBLE", "REAL", "FIXED")):
        return "number"
    if t.startswith("DATE") or t.startswith("TIMESTAMP") or t == "TIME":
        return "date"
    return "string"


def list_columns(company_id: str, table: str) -> list[dict[str, str]]:
    db, schema, name = parse_table(table)

    def _load() -> list[dict[str, str]]:
        client = get_client(company_id)
        df = client.query(
            f"SELECT COLUMN_NAME, DATA_TYPE FROM {db}.INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_NAME = %(name)s ORDER BY ORDINAL_POSITION",
            {"schema": schema, "name": name},
        )
        return [{"name": str(r["COLUMN_NAME"]), "type": map_type(str(r["DATA_TYPE"]))} for _, r in df.iterrows()]

    return _cached((company_id, "columns", db, schema, name), _load)


def jsonable(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if hasattr(v, "item"):  # numpy scalar
        try:
            return v.item()
        except Exception:
            pass
    return v


def distinct_values(company_id: str, table: str, column: str, q: str | None = None, limit: int = 500) -> list[Any]:
    tbl = qualified(table)
    col = validate_ident(column)
    sql = f"SELECT DISTINCT {col} AS V FROM {tbl} WHERE {col} IS NOT NULL"
    bind: dict[str, Any] = {}
    if q:
        sql += f" AND CONTAINS(LOWER(TO_VARCHAR({col})), LOWER(%(q)s))"
        bind["q"] = q
    sql += f" ORDER BY 1 LIMIT {int(limit)}"

    def _load() -> list[Any]:
        df = get_client(company_id).query(sql, bind, max_rows=limit)
        return [jsonable(v) for v in df["V"].tolist()]

    if q:
        return _load()
    return _cached((company_id, "values", tbl, col), _load)
