"use client";

import { useEffect, useMemo, useState } from "react";
import { format as fmtDate } from "date-fns";
import { formatParamValue } from "@/components/params/presets";
import { WidgetRenderer } from "@/components/widgets/WidgetRenderer";
import { runApi } from "@/lib/endpoints";
import type { Run, WidgetSpec } from "@/lib/types";
import { errorMessage } from "@/lib/utils";

declare global {
  interface Window {
    __REPORT_READY__?: boolean;
    __REPORT_ERROR__?: string;
  }
}

const ROW_PX = 40;
const GAP_PX = 10;

/**
 * Group widgets into horizontal bands: widgets whose vertical extents overlap share a band.
 * Each band is its own CSS grid with `break-inside: avoid`, so page breaks fall between
 * bands and never cut through a chart.
 */
function toBands(widgets: WidgetSpec[]) {
  const sorted = [...widgets].sort((a, b) => a.layout.y - b.layout.y || a.layout.x - b.layout.x);
  const bands: { top: number; bottom: number; widgets: WidgetSpec[] }[] = [];
  for (const w of sorted) {
    const top = w.layout.y;
    const bottom = w.layout.y + w.layout.h;
    const last = bands[bands.length - 1];
    if (last && top < last.bottom) {
      last.widgets.push(w);
      last.bottom = Math.max(last.bottom, bottom);
    } else {
      bands.push({ top, bottom, widgets: [w] });
    }
  }
  return bands;
}

function markReady(error?: string) {
  if (error) window.__REPORT_ERROR__ = error;
  window.__REPORT_READY__ = true;
}

export function PrintReport({ runId, token }: { runId: string; token: string | null }) {
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    window.__REPORT_READY__ = false;
    const load = token ? runApi.printGet(runId, token) : runApi.get(runId);
    load.then(setRun, (e) => {
      setError(errorMessage(e));
      markReady(errorMessage(e));
    });
  }, [runId, token]);

  useEffect(() => {
    if (!run) return;
    let cancelled = false;
    (async () => {
      try {
        await document.fonts.ready;
      } catch {}
      // Give ResponsiveContainer-based charts a moment to measure and paint.
      await new Promise((r) => setTimeout(r, 400));
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      if (!cancelled) markReady();
    })();
    return () => {
      cancelled = true;
    };
  }, [run]);

  const bands = useMemo(() => (run ? toBands(run.snapshot?.format.widgets ?? []) : []), [run]);

  if (error) {
    return (
      <div className="print-root mx-auto max-w-xl p-12 text-center text-sm text-red-700">
        Could not load this report: {error}
      </div>
    );
  }
  if (!run) return <div className="print-root p-12 text-center text-sm text-zinc-400">Loading report…</div>;
  if (!run.snapshot) {
    return <div className="print-root p-12 text-center text-sm text-red-700">This run has no data snapshot.</div>;
  }

  const snap = run.snapshot;
  const fmt = snap.format;
  const values = snap.values ?? run.values ?? {};
  const paramRows = fmt.params.map((p) => ({ label: p.label, value: formatParamValue(values[p.name]) }));
  const extra = Object.entries(values).filter(([k]) => !fmt.params.some((p) => p.name === k));
  const generatedAt = snap.generated_at ? new Date(snap.generated_at) : new Date(run.created_at);

  return (
    <div className="print-root min-h-screen bg-zinc-200 py-8 print:bg-white print:py-0">
      <div className="print-sheet mx-auto bg-white text-zinc-900 shadow-lg">
        <header className="mb-5 border-b-2 border-indigo-600 pb-4">
          <div className="flex items-start justify-between gap-6">
            <div>
              <div className="text-[11px] font-semibold tracking-[0.14em] text-indigo-600 uppercase">
                {snap.company_name}
              </div>
              <h1 className="mt-1 text-[22px] leading-tight font-semibold">{fmt.name}</h1>
              {fmt.description && <p className="mt-1 text-xs text-zinc-500">{fmt.description}</p>}
            </div>
            <div className="shrink-0 text-right text-[11px] text-zinc-500">
              <div>Generated</div>
              <div className="font-medium text-zinc-800">{fmtDate(generatedAt, "MMM d, yyyy · HH:mm")}</div>
            </div>
          </div>
          {(paramRows.length > 0 || extra.length > 0) && (
            <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs">
              {paramRows.map((r) => (
                <div key={r.label} className="flex gap-1.5">
                  <dt className="text-zinc-500">{r.label}:</dt>
                  <dd className="font-medium">{r.value}</dd>
                </div>
              ))}
              {extra.map(([k, v]) => (
                <div key={k} className="flex gap-1.5">
                  <dt className="text-zinc-500">{k}:</dt>
                  <dd className="font-medium">{formatParamValue(v)}</dd>
                </div>
              ))}
            </dl>
          )}
        </header>

        <main className="flex flex-col" style={{ gap: GAP_PX }}>
          {bands.map((band, bi) => {
            const rows = band.bottom - band.top;
            return (
              <section
                key={bi}
                className="print-band"
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(12, minmax(0, 1fr))",
                  gridTemplateRows: `repeat(${rows}, ${ROW_PX}px)`,
                  gap: GAP_PX,
                }}
              >
                {band.widgets.map((w) => {
                  const data = snap.data?.[w.id] ?? null;
                  const bare = w.type === "heading";
                  return (
                    <div
                      key={w.id}
                      className={
                        bare
                          ? "print-widget min-w-0 overflow-hidden"
                          : "print-widget min-w-0 overflow-hidden rounded-lg border border-zinc-200 bg-white"
                      }
                      style={{
                        gridColumn: `${w.layout.x + 1} / span ${Math.min(w.layout.w, 12 - w.layout.x)}`,
                        gridRow: `${w.layout.y - band.top + 1} / span ${w.layout.h}`,
                      }}
                    >
                      <WidgetRenderer spec={w} data={data} error={data?.error ?? null} mode="print" />
                    </div>
                  );
                })}
              </section>
            );
          })}
        </main>

        <footer className="mt-6 flex items-center justify-between border-t border-zinc-200 pt-3 text-[10px] text-zinc-400">
          <span>
            {snap.company_name} · {fmt.name}
            {fmt.client_scope ? ` · prepared for ${fmt.client_scope}` : ""}
          </span>
          <span>Generated by Agentic Reports · Run {run.id.slice(0, 8)}</span>
        </footer>
      </div>
    </div>
  );
}
