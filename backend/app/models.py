"""SQLModel tables for app metadata (SQLite). Business data stays in Snowflake."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Company(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str
    domain: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=utcnow)


class User(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    company_id: str = Field(foreign_key="company.id", index=True)
    email: str = Field(index=True, unique=True)
    full_name: str
    password_hash: str
    role: str = "designer"  # designer | viewer
    created_at: datetime = Field(default_factory=utcnow)


class SnowflakeConnection(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    company_id: str = Field(foreign_key="company.id", unique=True, index=True)
    account: str
    user: str
    warehouse: str | None = None
    role: str | None = None
    default_table: str | None = None
    token_encrypted: str
    last_tested_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utcnow)


class ReportFormatRow(SQLModel, table=True):
    __tablename__ = "report_format"

    id: str = Field(default_factory=new_id, primary_key=True)
    company_id: str = Field(foreign_key="company.id", index=True)
    created_by: str = Field(foreign_key="user.id")
    name: str
    body_json: str
    version: int = 1
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CustomArchetypeRow(SQLModel, table=True):
    __tablename__ = "custom_archetype"

    id: str = Field(default_factory=new_id, primary_key=True)
    company_id: str = Field(foreign_key="company.id", index=True)
    name: str
    description: str = ""
    def_json: str
    created_at: datetime = Field(default_factory=utcnow)


class Run(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    company_id: str = Field(foreign_key="company.id", index=True)
    format_id: str | None = Field(default=None, index=True)
    format_name: str
    values_json: str = "{}"
    status: str = "running"  # running | completed | failed
    error: str | None = None
    snapshot_json: str | None = None
    pdf_path: str | None = None
    created_by: str = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)
