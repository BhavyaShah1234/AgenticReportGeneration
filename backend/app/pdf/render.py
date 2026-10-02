"""Render a run to PDF with headless Chromium via the frontend `/print/{run_id}` page."""

from __future__ import annotations

from pathlib import Path

import httpx
from playwright.async_api import async_playwright

from app.auth.security import create_print_token
from app.config import get_settings

READY_TIMEOUT_MS = 60_000


class PdfRenderError(Exception):
    pass


def pdf_path_for(run_id: str) -> Path:
    return get_settings().storage_dir / "reports" / f"{run_id}.pdf"


async def frontend_reachable() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.get(get_settings().frontend_url)
        return True
    except Exception:
        return False


async def render_run_pdf(run_id: str) -> Path:
    s = get_settings()
    if not await frontend_reachable():
        raise PdfRenderError(f"PDF rendering failed: the frontend is not reachable at {s.frontend_url}")
    url = f"{s.frontend_url.rstrip('/')}/print/{run_id}?token={create_print_token(run_id)}"
    out = pdf_path_for(run_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                page = await browser.new_page(viewport={"width": 1240, "height": 1754})
                await page.emulate_media(media="print", reduced_motion="reduce")
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=READY_TIMEOUT_MS)
                if resp is not None and resp.status >= 400:
                    raise PdfRenderError(f"PDF rendering failed: print page returned HTTP {resp.status}")
                await page.wait_for_function("window.__REPORT_READY__ === true", timeout=READY_TIMEOUT_MS)
                await page.pdf(
                    path=str(out),
                    format="A4",
                    print_background=True,
                    margin={"top": "12mm", "bottom": "12mm", "left": "12mm", "right": "12mm"},
                )
            finally:
                await browser.close()
    except PdfRenderError:
        raise
    except Exception as e:
        msg = str(e).splitlines()[0] if str(e) else type(e).__name__
        if "Timeout" in type(e).__name__ or "Timeout" in msg:
            msg = "the print page did not signal window.__REPORT_READY__ within 60 s"
        raise PdfRenderError(f"PDF rendering failed: {msg}") from e
    return out
