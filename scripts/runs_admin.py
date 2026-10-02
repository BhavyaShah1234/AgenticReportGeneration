"""List or delete generated report runs (DB rows + PDF files).

    env -u PYTHONPATH backend/.venv/bin/python scripts/runs_admin.py list
    env -u PYTHONPATH backend/.venv/bin/python scripts/runs_admin.py delete <run_id> [<run_id> ...]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlmodel import Session, select  # noqa: E402

from app.db import engine  # noqa: E402
from app.models import Company, Run, User  # noqa: E402


def list_runs() -> None:
    with Session(engine) as s:
        for r in s.exec(select(Run).order_by(Run.created_at)).all():
            company = s.get(Company, r.company_id)
            user = s.get(User, r.created_by) if r.created_by else None
            values = json.loads(r.values_json or "{}")
            client = values.get("client") or "-"
            pdf = "pdf" if r.pdf_path and Path(r.pdf_path).exists() else "no-pdf"
            print(f"{r.id}  {r.created_at:%m-%d %H:%M}  {r.status:<9} {pdf:<6} {company.domain:<20} "
                  f"{(user.email if user else '-'):<28} {r.format_name[:26]:<26} {client}")


def delete_runs(ids: list[str]) -> None:
    with Session(engine) as s:
        for run_id in ids:
            r = s.get(Run, run_id)
            if r is None:
                print("not found:", run_id)
                continue
            if r.pdf_path and Path(r.pdf_path).exists():
                Path(r.pdf_path).unlink()
            s.delete(r)
            print("deleted:", run_id)
        s.commit()


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "list":
        list_runs()
    elif len(sys.argv) >= 3 and sys.argv[1] == "delete":
        delete_runs(sys.argv[2:])
    else:
        print(__doc__)
