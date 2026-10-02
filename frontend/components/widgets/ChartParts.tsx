"use client";

import type { ReactNode } from "react";
import type { TooltipPayloadEntry } from "recharts";
import { useElementSize, type Size } from "./useElementSize";
import { CHART } from "./palette";
import { formatValue, humanize, type ValueFormat } from "./format";

export const AXIS_TICK = { fill: CHART.muted, fontSize: 11 } as const;

export function ChartTooltip({
  active,
  payload,
  label,
  fmt,
  raw,
}: {
  active?: boolean;
  payload?: ReadonlyArray<TooltipPayloadEntry>;
  label?: unknown;
  fmt: ValueFormat;
  /** show series names as-is (they are data values, not column names) */
  raw?: boolean;
}) {
  if (!active || !payload?.length) return null;
  const items = payload.filter((p) => p.value !== null && p.value !== undefined);
  return (
    <div className="min-w-32 rounded-md border border-zinc-200 bg-white/95 px-2.5 py-2 text-xs shadow-md">
      {label !== undefined && label !== "" && <div className="mb-1 font-medium text-zinc-900">{String(label)}</div>}
      <div className="space-y-0.5">
        {items.map((p, i) => (
          <div key={`${String(p.dataKey ?? p.name)}-${i}`} className="flex items-center gap-2">
            <span
              className="inline-block h-2 w-2 shrink-0 rounded-full"
              style={{ background: (p.color as string) || (p.fill as string) || (p.payload?.fill as string) }}
            />
            <span className="truncate text-zinc-600">{raw ? String(p.name ?? p.dataKey ?? "") : humanize(String(p.name ?? p.dataKey ?? ""))}</span>
            <span className="ml-auto pl-3 font-medium tabular-nums text-zinc-900">{formatValue(p.value, fmt)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function LegendRow({ items, raw }: { items: { name: string; color: string }[]; raw?: boolean }) {
  if (items.length < 2) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-1 pb-1 text-[11px] text-zinc-600">
      {items.map((it) => (
        <span key={it.name} className="inline-flex max-w-48 items-center gap-1.5">
          <span className="inline-block h-2 w-2 shrink-0 rounded-sm" style={{ background: it.color }} />
          <span className="truncate">{raw ? it.name : humanize(it.name)}</span>
        </span>
      ))}
    </div>
  );
}

export function EmptyState({ message = "No data for the selected filters" }: { message?: string }) {
  return (
    <div className="flex h-full w-full items-center justify-center p-3 text-center text-xs text-zinc-400">{message}</div>
  );
}

/** Rough y-axis width from the longest formatted tick. */
export function yAxisWidth(labels: string[]): number {
  const longest = labels.reduce((m, s) => Math.max(m, s.length), 0);
  return Math.min(90, Math.max(32, longest * 6.5 + 10));
}

/** Legend row on top, measured chart area below; renders children only once sized. */
export function ChartBox({ legend, children }: { legend?: ReactNode; children: (size: Size) => ReactNode }) {
  const [ref, size] = useElementSize<HTMLDivElement>();
  return (
    <div className="flex h-full w-full flex-col">
      {legend}
      <div ref={ref} className="relative min-h-0 flex-1">
        {size.width > 0 && size.height > 0 ? children(size) : null}
      </div>
    </div>
  );
}
