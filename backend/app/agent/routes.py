"""Agent routes: NL -> widget / report format, and LLM health."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.agent import service
from app.agent.llm import get_llm
from app.auth.deps import current_user, require_designer
from app.models import User
from app.schemas.api import AgentHealthOut, AgentReportIn, AgentReportOut, AgentWidgetIn, AgentWidgetOut
from app.snowflake import service as sf

router = APIRouter(prefix="/agent", tags=["agent"])


def _table(user: User, table: str | None) -> str:
    try:
        return sf.qualified(table or sf.default_table(user.company_id))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


def _http(e: Exception) -> HTTPException:
    if isinstance(e, sf.NotConnected):
        return HTTPException(409, str(e))
    if isinstance(e, service.AgentError):
        return HTTPException(422, str(e))
    return HTTPException(502, f"Agent failed: {e}"[:500])


@router.get("/health", response_model=AgentHealthOut)
async def agent_health(user: User = Depends(current_user)) -> AgentHealthOut:
    llm = get_llm()
    ok, err = await llm.health()
    return AgentHealthOut(ok=ok, model=llm.model, base_url=llm.base_url, error=err)


@router.post("/widget", response_model=AgentWidgetOut)
async def agent_widget(body: AgentWidgetIn, user: User = Depends(require_designer)) -> AgentWidgetOut:
    table = _table(user, body.table)
    try:
        widget, explanation = await service.design_widget(user.company_id, body.prompt, table, body.params, body.existing_widgets)
    except Exception as e:
        raise _http(e) from e
    return AgentWidgetOut(widget=widget, explanation=explanation)


@router.post("/report", response_model=AgentReportOut)
async def agent_report(body: AgentReportIn, user: User = Depends(require_designer)) -> AgentReportOut:
    table = _table(user, body.table)
    try:
        fmt, explanation = await service.design_report(user.company_id, body.prompt, table)
    except Exception as e:
        raise _http(e) from e
    return AgentReportOut(format=fmt, explanation=explanation)
