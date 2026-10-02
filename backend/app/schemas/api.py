"""Request/response models for the HTTP API (docs/API.md). Report contracts live in report.py."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.report import (
    ArchetypeConfig,
    DataSource,
    ParamDef,
    ReportFormatBody,
    WidgetData,
    WidgetSpec,
    WidgetType,
)

Role = Literal["designer", "viewer"]
RunStatus = Literal["running", "completed", "failed"]


# --- auth -------------------------------------------------------------------
class SignupIn(BaseModel):
    company_name: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=6)
    role: Role = "designer"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class CompanyOut(BaseModel):
    id: str
    name: str
    domain: str


class Me(BaseModel):
    id: str
    email: str
    full_name: str
    role: Role
    company: CompanyOut
    snowflake_connected: bool


# --- connection ---------------------------------------------------------------
class ConnectionOut(BaseModel):
    connected: bool
    account: str | None = None
    user: str | None = None
    warehouse: str | None = None
    role: str | None = None
    default_table: str | None = None
    last_tested_at: datetime | None = None


class ConnectionIn(BaseModel):
    account: str = Field(min_length=1)
    user: str = Field(min_length=1)
    token: str | None = Field(default=None, description="PAT; may be omitted to keep the stored token")
    warehouse: str | None = None
    role: str | None = None
    default_table: str | None = None


class ConnectionTestOut(BaseModel):
    ok: bool
    info: dict[str, str] | None = None
    error: str | None = None


# --- schema -----------------------------------------------------------------
class TableOut(BaseModel):
    table: str
    kind: Literal["TABLE", "VIEW"]


# --- archetypes / widgets ------------------------------------------------------
class CustomArchetypeIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    base: ArchetypeConfig | None = None
    sql: str | None = None
    suggested_widgets: list[WidgetType] = Field(default_factory=list)


class PreviewIn(BaseModel):
    widget: WidgetSpec
    params: list[ParamDef] = Field(default_factory=list)
    values: dict[str, Any] = Field(default_factory=dict)
    default_source: DataSource | None = None


# --- runs -------------------------------------------------------------------
class RunIn(BaseModel):
    format_id: str
    values: dict[str, Any] = Field(default_factory=dict)


class RunSnapshot(BaseModel):
    format: ReportFormatBody
    values: dict[str, Any]
    data: dict[str, WidgetData]
    generated_at: datetime
    company_name: str


class RunSummary(BaseModel):
    id: str
    format_id: str | None
    format_name: str
    values: dict[str, Any]
    status: RunStatus
    error: str | None = None
    created_by_name: str
    created_at: datetime
    pdf_url: str | None = None


class RunOut(RunSummary):
    snapshot: RunSnapshot | None = None


# --- agent ------------------------------------------------------------------
class AgentWidgetIn(BaseModel):
    prompt: str = Field(min_length=1)
    table: str | None = None
    params: list[ParamDef] = Field(default_factory=list)
    existing_widgets: list[WidgetSpec] = Field(default_factory=list)


class AgentWidgetOut(BaseModel):
    widget: WidgetSpec
    explanation: str


class AgentReportIn(BaseModel):
    prompt: str = Field(min_length=1)
    table: str | None = None


class AgentReportOut(BaseModel):
    format: ReportFormatBody
    explanation: str


class AgentHealthOut(BaseModel):
    ok: bool
    model: str
    base_url: str
    error: str | None = None
