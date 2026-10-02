"""Report format CRUD. Designers write; everyone in the company reads."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from app.auth.deps import current_user, require_designer
from app.db import get_session
from app.models import ReportFormatRow, User, utcnow
from app.schemas.report import ReportFormat, ReportFormatBody

router = APIRouter(prefix="/formats", tags=["formats"])


def to_format(row: ReportFormatRow) -> ReportFormat:
    body = ReportFormatBody.model_validate_json(row.body_json)
    return ReportFormat(
        **body.model_dump(),
        id=row.id,
        company_id=row.company_id,
        created_by=row.created_by,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def check_body(body: ReportFormatBody) -> None:
    ids = [w.id for w in body.widgets]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "Widget ids must be unique")
    names = [p.name for p in body.params]
    if len(names) != len(set(names)):
        raise HTTPException(400, "Param names must be unique")
    if not body.name.strip():
        raise HTTPException(400, "Name is required")


def get_row(session: Session, user: User, format_id: str) -> ReportFormatRow:
    row = session.get(ReportFormatRow, format_id)
    if row is None or row.company_id != user.company_id:
        raise HTTPException(404, "Report format not found")
    return row


@router.get("", response_model=list[ReportFormat])
def list_formats(user: User = Depends(current_user), session: Session = Depends(get_session)) -> list[ReportFormat]:
    rows = session.exec(
        select(ReportFormatRow)
        .where(ReportFormatRow.company_id == user.company_id)
        .order_by(col(ReportFormatRow.updated_at).desc())
    ).all()
    return [to_format(r) for r in rows]


@router.post("", response_model=ReportFormat)
def create_format(
    body: ReportFormatBody, user: User = Depends(require_designer), session: Session = Depends(get_session)
) -> ReportFormat:
    check_body(body)
    row = ReportFormatRow(company_id=user.company_id, created_by=user.id, name=body.name, body_json=body.model_dump_json())
    session.add(row)
    session.commit()
    session.refresh(row)
    return to_format(row)


@router.get("/{format_id}", response_model=ReportFormat)
def get_format(format_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)) -> ReportFormat:
    return to_format(get_row(session, user, format_id))


@router.put("/{format_id}", response_model=ReportFormat)
def update_format(
    format_id: str, body: ReportFormatBody, user: User = Depends(require_designer), session: Session = Depends(get_session)
) -> ReportFormat:
    check_body(body)
    row = get_row(session, user, format_id)
    row.name = body.name
    row.body_json = body.model_dump_json()
    row.version += 1
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return to_format(row)


@router.delete("/{format_id}")
def delete_format(format_id: str, user: User = Depends(require_designer), session: Session = Depends(get_session)) -> dict:
    row = get_row(session, user, format_id)
    session.delete(row)
    session.commit()
    return {"ok": True}


@router.post("/{format_id}/duplicate", response_model=ReportFormat)
def duplicate_format(
    format_id: str, user: User = Depends(require_designer), session: Session = Depends(get_session)
) -> ReportFormat:
    src = get_row(session, user, format_id)
    body = ReportFormatBody.model_validate_json(src.body_json)
    body.name = f"{body.name} (copy)"
    row = ReportFormatRow(company_id=user.company_id, created_by=user.id, name=body.name, body_json=body.model_dump_json())
    session.add(row)
    session.commit()
    session.refresh(row)
    return to_format(row)
