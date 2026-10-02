"""Runs (generated reports) + print endpoint used by the PDF renderer."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session, col, select

from app.auth.deps import current_user
from app.auth.security import verify_print_token
from app.catalog import service as cat
from app.db import get_session
from app.models import ReportFormatRow, Run, User
from app.runs import service
from app.schemas.api import RunIn, RunOut, RunSummary
from app.schemas.report import ReportFormatBody
from app.snowflake import service as sf

router = APIRouter(tags=["runs"])


def _get_run(session: Session, user: User, run_id: str) -> Run:
    run = session.get(Run, run_id)
    if run is None or run.company_id != user.company_id:
        raise HTTPException(404, "Run not found")
    return run


@router.post("/runs", response_model=RunOut)
async def create_run(body: RunIn, user: User = Depends(current_user), session: Session = Depends(get_session)) -> RunOut:
    row = session.get(ReportFormatRow, body.format_id)
    if row is None or row.company_id != user.company_id:
        raise HTTPException(404, "Report format not found")
    fmt = ReportFormatBody.model_validate_json(row.body_json)
    try:
        values = cat.normalize_values(fmt.params, body.values)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    missing = cat.missing_required(fmt.params, values)
    if missing:
        raise HTTPException(400, f"Missing required parameter(s): {', '.join(missing)}")
    try:
        run_id = await service.generate(user.company_id, user, row.id, fmt.name, fmt, values)
    except sf.NotConnected as e:
        raise HTTPException(409, str(e)) from e
    session.expire_all()
    return service.run_out(session, session.get(Run, run_id))


@router.get("/runs", response_model=list[RunSummary])
def list_runs(
    format_id: str | None = None,
    limit: int = Query(default=100, le=500),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[RunSummary]:
    q = select(Run).where(Run.company_id == user.company_id)
    if format_id:
        q = q.where(Run.format_id == format_id)
    rows = session.exec(q.order_by(col(Run.created_at).desc()).limit(limit)).all()
    return [service.run_summary(session, r) for r in rows]


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)) -> RunOut:
    return service.run_out(session, _get_run(session, user, run_id))


@router.get("/runs/{run_id}/pdf")
def get_run_pdf(
    run_id: str, download: int = 0, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> FileResponse:
    run = _get_run(session, user, run_id)
    if not run.pdf_path or not Path(run.pdf_path).exists():
        raise HTTPException(404, run.error or "PDF not available for this run")
    filename = service.pdf_filename(run)
    return FileResponse(
        run.pdf_path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="attachment" if download else "inline",
    )


@router.get("/print/runs/{run_id}", response_model=RunOut)
def print_run(run_id: str, token: str = Query(...), session: Session = Depends(get_session)) -> RunOut:
    if not verify_print_token(token, run_id):
        raise HTTPException(401, "Invalid or expired print token")
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return service.run_out(session, run)
