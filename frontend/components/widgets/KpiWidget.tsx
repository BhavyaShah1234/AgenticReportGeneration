"use client";

import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { EmptyState } from "./ChartParts";
import { widgetFormat, type WidgetBodyProps } from "./chartData";
import { formatPercentDelta, formatShort, formatValue, toNumber } from "./format";
import { CHART } from "./palette";

/**
 * Stat tile: big value, signed delta badge vs the comparison period, period label.
 * Reads WidgetData.meta {value, previous, delta_pct, period_label, previous_label} and falls
 * back to the first row's encoding.value. `options.extra.lower_is_better` flips the colors.
 */
export function KpiWidget({ spec, data }: WidgetBodyProps) {
  const fmt = widgetFormat(spec);
  const meta = data.meta ?? {};
  const valueKey = data.encoding?.value ?? "VALUE";
  const value = toNumber(meta.value ?? data.rows[0]?.[valueKey]);
  if (value === null && !data.rows.length) return <EmptyState />;

  const previous = toNumber(meta.previous);
  const delta = toNumber(meta.delta_pct);
  const lowerIsBetter = spec.options?.extra?.lower_is_better === true;
  const direction = delta === null || delta === 0 ? 0 : delta > 0 ? 1 : -1;
  const good = direction === 0 ? null : (direction > 0) !== lowerIsBetter;
  const Icon = direction > 0 ? ArrowUpRight : direction < 0 ? ArrowDownRight : Minus;
  const periodLabel = typeof meta.period_label === "string" ? meta.period_label : null;
  const prevLabel = typeof meta.previous_label === "string" ? meta.previous_label : null;

  return (
    <div className="@container flex h-full w-full flex-col justify-center gap-1 px-4 pb-3"title={formatValue(value, fmt)}>
      <div className="truncate text-3xl font-semibold leading-tight tracking-tight text-zinc-900 @[16rem]:text-4xl">
        {formatShort(value, fmt)}
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        {delta !== null && (
          <span
            className="inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 font-medium"
            style={{
              color: good === null ? CHART.textSecondary : good ? CHART.good : CHART.bad,
              background: good === null ? CHART.neutralBg : good ? CHART.goodBg : CHART.badBg,
            }}
            aria-label={`${good === null ? "No change" : good ? "Improved" : "Declined"} ${formatPercentDelta(delta)}`}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {formatPercentDelta(delta)}
          </span>
        )}
        {previous !== null && (
          <span className="truncate text-zinc-500">
            vs {formatShort(previous, fmt)}
            {prevLabel ? ` in ${prevLabel}` : ""}
          </span>
        )}
      </div>
      {periodLabel && <div className="truncate text-[11px] text-zinc-400">{periodLabel}</div>}
    </div>
  );
}
