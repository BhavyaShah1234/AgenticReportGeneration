"use client";

import { Cell, Pie, PieChart, Tooltip } from "recharts";
import { ChartBox, ChartTooltip, EmptyState } from "./ChartParts";
import { toSlices, widgetFormat, type WidgetBodyProps } from "./chartData";
import { formatShort, formatValue } from "./format";
import { CHART, seriesColor } from "./palette";

/** Pie and donut (spec.type === "donut"). Legend lists every slice with its share. */
export function PieWidget({ spec, data, mode }: WidgetBodyProps) {
  const slices = toSlices(data);
  const fmt = widgetFormat(spec);
  const donut = spec.type === "donut";
  if (!slices.length) return <EmptyState />;
  const total = slices.reduce((a, s) => a + s.value, 0);
  const colors = slices.map((s, i) => seriesColor(i, s.name, spec.options?.color));
  const showLegend = spec.options?.show_legend !== false;

  return (
    <ChartBox>
      {({ width, height }) => {
        const side = width > height * 1.5 && showLegend; // legend beside the pie when wide
        const pieW = side ? Math.min(height, width * 0.55) : width;
        const pieH = side ? height : showLegend ? Math.max(80, height - Math.min(slices.length, 4) * 18 - 8) : height;
        const r = Math.max(20, Math.min(pieW, pieH) / 2 - 6);
        const legend = showLegend && (
          <ul className={side ? "min-w-0 flex-1 space-y-1 self-center pr-2" : "grid grid-cols-2 gap-x-3 gap-y-0.5 px-2"}>
            {slices.map((s, i) => (
              <li key={s.name} className="flex min-w-0 items-center gap-1.5 text-[11px] text-zinc-600">
                <span className="inline-block h-2 w-2 shrink-0 rounded-sm" style={{ background: colors[i] }} />
                <span className="truncate">{s.name}</span>
                <span className="ml-auto pl-1 tabular-nums text-zinc-900">{formatValue(s.value / total, "percent")}</span>
              </li>
            ))}
          </ul>
        );
        return (
          <div className={side ? "flex h-full w-full items-center" : "flex h-full w-full flex-col"}>
            <div className="relative" style={{ width: pieW, height: pieH }}>
              <PieChart width={pieW} height={pieH}>
                <Pie
                  data={slices}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={r}
                  innerRadius={donut ? r * 0.62 : 0}
                  stroke={CHART.surface}
                  strokeWidth={2}
                  paddingAngle={0}
                  isAnimationActive={mode !== "print"}
                  label={
                    spec.options?.show_labels
                      ? ({ percent }: { percent?: number }) => formatValue(percent ?? 0, "percent")
                      : false
                  }
                  labelLine={false}
                >
                  {slices.map((s, i) => (
                    <Cell key={s.name} fill={colors[i]} />
                  ))}
                </Pie>
                {mode !== "print" && (
                  <Tooltip content={(p) => <ChartTooltip active={p.active} payload={p.payload} label={p.label} fmt={fmt} raw />} isAnimationActive={false} />
                )}
              </PieChart>
              {donut && (
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-[10px] uppercase tracking-wide text-zinc-500">Total</span>
                  <span className="text-sm font-semibold text-zinc-900">{formatShort(total, fmt)}</span>
                </div>
              )}
            </div>
            {legend}
          </div>
        );
      }}
    </ChartBox>
  );
}
