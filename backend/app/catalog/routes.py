"""Archetype catalog + widget preview routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session

from app.auth.deps import current_user, require_designer
from app.catalog import service as cat
from app.db import get_session
from app.models import CustomArchetypeRow, User, new_id
from app.schemas.api import CustomArchetypeIn, PreviewIn
from app.schemas.report import ArchetypeSpec, CustomArchetypeDef, DataSource, WidgetData
from app.snowflake import service as sf

router = APIRouter(tags=["archetypes"])


@router.get("/archetypes", response_model=list[ArchetypeSpec])
def get_archetypes(user: User = Depends(current_user), session: Session = Depends(get_session)) -> list[ArchetypeSpec]:
    return cat.list_archetypes(cat.custom_defs(user.company_id, session))


@router.post("/archetypes/custom", response_model=ArchetypeSpec)
def create_custom(
    body: CustomArchetypeIn, user: User = Depends(require_designer), session: Session = Depends(get_session)
) -> ArchetypeSpec:
    if bool(body.base) == bool(body.sql and body.sql.strip()):
        raise HTTPException(400, "Provide exactly one of `base` or `sql`")
    if body.base is not None:
        if body.base.id not in cat.builtin_ids():
            raise HTTPException(400, f"Unknown builtin archetype '{body.base.id}'")
    else:
        try:
            cat.get_engine().validate_custom_sql(body.sql)
        except ValueError as e:
            raise HTTPException(400, f"Invalid SQL: {e}") from e
    row_id = new_id()
    d = CustomArchetypeDef(
        id=row_id,
        name=body.name.strip(),
        description=body.description,
        base=body.base,
        sql=body.sql.strip() if body.sql else None,
        suggested_widgets=body.suggested_widgets,
    )
    row = CustomArchetypeRow(id=row_id, company_id=user.company_id, name=d.name, description=d.description, def_json=d.model_dump_json())
    session.add(row)
    session.commit()
    specs = cat.list_archetypes([d])
    for s in specs:
        if s.id in (f"custom:{row_id}", row_id):
            return s
    raise HTTPException(500, "Archetype engine did not return the new custom archetype")


@router.delete("/archetypes/custom/{arch_id}")
def delete_custom(arch_id: str, user: User = Depends(require_designer), session: Session = Depends(get_session)) -> dict:
    row = session.get(CustomArchetypeRow, arch_id.removeprefix("custom:"))
    if row is None or row.company_id != user.company_id:
        raise HTTPException(404, "Custom archetype not found")
    session.delete(row)
    session.commit()
    return {"ok": True}


@router.post("/widgets/preview", response_model=WidgetData)
async def preview_widget(body: PreviewIn, user: User = Depends(current_user)) -> WidgetData:
    w = body.widget
    if w.options.narrative:
        return WidgetData(
            widget_id=w.id,
            meta={"text": w.options.text or "_The narrative summary is written by the AI agent when the report is generated._"},
        )
    if w.type in cat.DATA_LESS_TYPES and w.archetype is None:
        return WidgetData(widget_id=w.id, meta={"text": w.options.text or ""})
    try:
        values = cat.normalize_values(body.params, body.values)
    except ValueError as e:
        return WidgetData(widget_id=w.id, error=str(e))
    try:
        client = await run_in_threadpool(sf.get_client, user.company_id)
    except Exception as e:
        return WidgetData(widget_id=w.id, error=str(e))
    default_source = body.default_source or DataSource(table=sf.default_table(user.company_id))
    customs = cat.custom_map(cat.custom_defs(user.company_id))
    return await run_in_threadpool(
        lambda: cat.execute(client, w, param_defs=body.params, values=values, default_source=default_source, customs=customs)
    )
