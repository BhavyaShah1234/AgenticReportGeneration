"""Identifier validation, quoting and small SQL builders shared by archetypes and the engine.

Rules: every identifier (table part or column) must match `IDENT_RE` and, when the table's
column list is known, exist in it. Identifiers are emitted double-quoted and uppercase.
Values are never interpolated: they go into the bind dict as pyformat `%(name)s`.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Literal

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

Agg = Literal["sum", "avg", "count", "count_distinct", "min", "max"]
Grain = Literal["day", "week", "month", "quarter", "year"]

_AGG_SQL = {"sum": "SUM", "avg": "AVG", "count": "COUNT", "min": "MIN", "max": "MAX"}
_GRAINS = {"day", "week", "month", "quarter", "year"}


class IdentifierError(ValueError):
    pass


def check_ident(name: str) -> str:
    """Validate a bare identifier and return it uppercased (unquoted)."""
    if not isinstance(name, str) or not IDENT_RE.match(name):
        raise IdentifierError(f"Invalid identifier: {name!r}")
    return name.upper()


def quote_table(table: str) -> str:
    """`db.schema.name` -> `"DB"."SCHEMA"."NAME"` (1 to 3 parts, each validated)."""
    if not isinstance(table, str):
        raise IdentifierError(f"Invalid table name: {table!r}")
    parts = table.strip().split(".")
    if not 1 <= len(parts) <= 3:
        raise IdentifierError(f"Invalid table name: {table!r}")
    return ".".join(f'"{check_ident(p)}"' for p in parts)


def normalize_table(table: str) -> str:
    """Canonical unquoted uppercase name, used as a cache key."""
    quote_table(table)
    return ".".join(p.upper() for p in table.strip().split("."))


def col(name: str, columns: dict[str, str] | None) -> str:
    """Validate a column against the table's columns and return it double-quoted."""
    up = check_ident(name)
    if columns and up not in columns:
        raise IdentifierError(f"Unknown column {name!r}. Available: {', '.join(sorted(columns))}")
    return f'"{up}"'


def agg_sql(agg: str, expr: str) -> str:
    if agg == "count_distinct":
        return f"COUNT(DISTINCT {expr})"
    if agg not in _AGG_SQL:
        raise ValueError(f"Unsupported aggregation {agg!r}")
    return f"{_AGG_SQL[agg]}({expr})"


def trunc_sql(grain: str, expr: str) -> str:
    if grain not in _GRAINS:
        raise ValueError(f"Unsupported grain {grain!r}")
    return f"DATE_TRUNC('{grain}', {expr})::DATE"


# ---------------------------------------------------------------------------
# Date window helpers (pure Python; results are bound as values)
# ---------------------------------------------------------------------------


def _month_end(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def _add_months(d: date, n: int) -> date:
    idx = d.year * 12 + d.month - 1 + n
    y, m = divmod(idx, 12)
    return date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def is_month_aligned(start: date, end: date) -> bool:
    return start.day == 1 and end == _month_end(end.year, end.month)


def previous_window(start: date, end: date, compare: str = "previous_period") -> tuple[date, date]:
    """The comparison window for [start, end].

    previous_year: same dates one year earlier. previous_period: the equal-length window
    right before; for whole-month ranges it shifts by whole months (2004 -> 2003).
    """
    if compare == "previous_year":
        return _add_months(start, -12), (
            _month_end(end.year - 1, end.month) if end == _month_end(end.year, end.month) else _add_months(end, -12)
        )
    if is_month_aligned(start, end):
        n = (end.year - start.year) * 12 + end.month - start.month + 1
        ps = _add_months(start, -n)
        return ps, start - timedelta(days=1)
    length = (end - start).days + 1
    return start - timedelta(days=length), start - timedelta(days=1)


def period_label(start: date, end: date) -> str:
    """Human label: '2004', 'Q1 2004', 'Jan 2004', 'Jan–Jun 2004' or 'Jan 6, 2003 – May 31, 2005'."""
    if is_month_aligned(start, end):
        months = (end.year - start.year) * 12 + end.month - start.month + 1
        if start.month == 1 and months == 12:
            return str(start.year)
        if months == 3 and start.month in (1, 4, 7, 10):
            return f"Q{(start.month - 1) // 3 + 1} {start.year}"
        if months == 1:
            return start.strftime("%b %Y")
        if start.year == end.year:
            return f"{start.strftime('%b')}–{end.strftime('%b %Y')}"
        return f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}"
    if start == end:
        return start.strftime("%b %-d, %Y")
    return f"{start.strftime('%b %-d, %Y')} – {end.strftime('%b %-d, %Y')}"


def grain_bucket_end(start: date, grain: str) -> date:
    """Last day of the grain bucket starting at `start`."""
    if grain == "day":
        return start
    if grain == "week":
        return start + timedelta(days=6)
    n = {"month": 1, "quarter": 3, "year": 12}[grain]
    return _add_months(start, n) - timedelta(days=1)
