"""Report generation: execute every widget, write narratives, snapshot, render PDF."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session

from app.agent import service as agent
from app.catalog import service as cat
from app.db import engine
from app.models import Company, Run, User
from app.pdf.render import PdfRenderError, render_run_pdf
from app.schemas.api import RunOut, RunSnapshot, RunSummary
from app.schemas.report import DataSource, ReportFormatBody, WidgetData, WidgetSpec
from app.snowflake import service as sf

log = logging.getLogger(__name__)
MAX_WORKERS = 4


def run_summary(session: Session, run: Run) -> RunSummary:
    user = session.get(User, run.created_by)
    pdf_ok = bool(run.pdf_path and Path(run.pdf_path).exists())
    return RunSummary(
        id=run.id,
        format_id=run.format_id,
        format_name=run.format_name,
        values=json.loads(run.values_json or "{}"),
        status=run.status,  # type: ignore[arg-type]
        error=run.error,
        created_by_name=user.full_name if user else "Unknown",
        created_at=run.created_at,
        pdf_url=f"/api/runs/{run.id}/pdf" if pdf_ok else None,
    )


def run_out(session: Session, run: Run) -> RunOut:
    summary = run_summary(session, run)
    snap = RunSnapshot.model_validate_json(run.snapshot_json) if run.snapshot_json else None
    return RunOut(**summary.model_dump(), snapshot=snap)


def pdf_filename(run: Run) -> str:
    values = json.loads(run.values_json or "{}")
    subject = next((v for v in values.values() if isinstance(v, str) and v.strip()), None)
    parts = [run.format_name, subject, run.created_at.strftime("%Y-%m-%d")]
    clean = [re.sub(r"[^A-Za-z0-9]+", "_", p).strip("_") for p in parts if p]
    return "-".join(p for p in clean if p) + ".pdf"


def _execute_all(client, body: ReportFormatBody, values: dict[str, Any], default_source: DataSource, customs) -> dict[str, WidgetData]:
    data: dict[str, WidgetData] = {}
    data_widgets: list[WidgetSpec] = []
    for w in body.widgets:
        if w.options.narrative or (w.type in cat.DATA_LESS_TYPES and w.archetype is None):
            data[w.id] = WidgetData(widget_id=w.id, meta={"text": w.options.text or ""})
        else:
            data_widgets.append(w)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            w.id: pool.submit(
                cat.execute, client, w, param_defs=body.params, values=values, default_source=default_source, customs=customs
            )
            for w in data_widgets
        }
        for wid, fut in futures.items():
            try:
                data[wid] = fut.result()
            except Exception as e:
                data[wid] = WidgetData(widget_id=wid, error=str(e)[:500])
    return data


async def generate(company_id: str, user: User, format_id: str, format_name: str, body: ReportFormatBody, values: dict[str, Any]) -> str:
    """Create and fully process a run; returns the run id. Raises nothing after the run row exists."""
    client = await run_in_threadpool(sf.get_client, company_id)  # raises NotConnected before any row is created
    with Session(engine) as s:
        run = Run(
            company_id=company_id,
            format_id=format_id,
            format_name=format_name,
            values_json=json.dumps(values),
            status="running",
            created_by=user.id,
        )
        s.add(run)
        s.commit()
        run_id = run.id
        company = s.get(Company, company_id)
        company_name = company.name if company else ""

    error: str | None = None
    status = "completed"
    snapshot: RunSnapshot | None = None
    try:
        default_source = body.default_source or DataSource(table=sf.default_table(company_id))
        customs = cat.custom_map(cat.custom_defs(company_id))
        data = await run_in_threadpool(_execute_all, client, body, values, default_source, customs)
        for w in body.widgets:
            if w.type == "text" and w.options.narrative:
                text, source = await agent.write_narrative(format_name, values, w, body.widgets, data)
                data[w.id] = WidgetData(widget_id=w.id, meta={"text": text, "source": source})
        snapshot = RunSnapshot(
            format=body, values=values, data=data, generated_at=datetime.now(UTC), company_name=company_name
        )
    except Exception as e:
        log.exception("run %s failed during execution", run_id)
        status, error = "failed", f"Generation failed: {e}"[:1000]

    with Session(engine) as s:
        run = s.get(Run, run_id)
        run.snapshot_json = snapshot.model_dump_json() if snapshot else None
        run.status, run.error = ("running", None) if snapshot else (status, error)
        s.add(run)
        s.commit()

    if snapshot is not None:
        try:
            path = await render_run_pdf(run_id)
            status, error, pdf_path = "completed", None, str(path)
        except PdfRenderError as e:
            status, error, pdf_path = "failed", str(e), None
        except Exception as e:  # pragma: no cover - unexpected playwright failures
            status, error, pdf_path = "failed", f"PDF rendering failed: {e}"[:1000], None
        with Session(engine) as s:
            run = s.get(Run, run_id)
            run.status, run.error, run.pdf_path = status, error, pdf_path
            s.add(run)
            s.commit()
    return run_id
