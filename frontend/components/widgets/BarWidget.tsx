"use client";

import { Bar, BarChart, CartesianGrid, LabelList, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS_TICK, ChartBox, ChartTooltip, EmptyState, LegendRow, yAxisWidth } from "./ChartParts";
import { extraFlag, toCartesian, widgetFormat, type WidgetBodyProps } from "./chartData";
import { formatShort } from "./format";
import { CHART, seriesColor } from "./palette";

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

/** Bar / column chart. Handles `stacked_bar` and `options.extra.horizontal`. */
export function BarWidget({ spec, data, mode }: WidgetBodyProps) {
  const shape = toCartesian(data);
  const fmt = widgetFormat(spec);
  const stacked = spec.type === "stacked_bar" || extraFlag(spec, "stacked") === true;
  const animate = mode !== "print";
  if (!shape.rows.length || !shape.keys.length) return <EmptyState />;

  const labels = shape.rows.map((r) => String(r[shape.xKey]));
  const longLabels = labels.reduce((a, s) => a + s.length, 0) / labels.length > 10;
  const horizontal = extraFlag(spec, "horizontal") ?? (!shape.isTime && longLabels && labels.length > 4);
  const colors = shape.keys.map((k, i) => seriesColor(i, k, spec.options?.color));
  const legend =
    spec.options?.show_legend !== false ? (
      <LegendRow raw={!shape.keysAreColumns} items={shape.keys.map((k, i) => ({ name: k, color: colors[i] }))} />
    ) : null;

  // y ticks: estimate width from the largest total so long currency labels don't clip
  const maxVal = Math.max(
    ...shape.rows.map((r) =>
      stacked
        ? shape.keys.reduce((a, k) => a + Math.max(0, Number(r[k]) || 0), 0)
        : Math.max(...shape.keys.map((k) => Number(r[k]) || 0)),
    ),
  );
  const valueAxisWidth = yAxisWidth([formatShort(maxVal, fmt)]);
  const catAxisWidth = Math.min(160, Math.max(48, Math.max(...labels.map((l) => Math.min(l.length, 24))) * 6.2 + 8));
  const showLabels = spec.options?.show_labels && !stacked;

  return (
    <ChartBox legend={legend}>
      {({ width, height }) => (
        <BarChart
          width={width}
          height={height}
          data={shape.rows}
          layout={horizontal ? "vertical" : "horizontal"}
          margin={{ top: showLabels && !horizontal ? 16 : 6, right: showLabels && horizontal ? 44 : 12, bottom: 0, left: 0 }}
          barCategoryGap="22%"
          barGap={2}
        >
          <CartesianGrid stroke={CHART.grid} vertical={horizontal} horizontal={!horizontal} />
          {horizontal ? (
            <>
              <XAxis
                type="number"
                tick={AXIS_TICK}
                tickFormatter={(v) => formatShort(v, fmt)}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey={shape.xKey}
                tick={AXIS_TICK}
                width={catAxisWidth}
                tickFormatter={(v) => truncate(String(v), 24)}
                axisLine={{ stroke: CHART.axis }}
                tickLine={false}
                interval={0}
              />
            </>
          ) : (
            <>
              <XAxis
                dataKey={shape.xKey}
                tick={AXIS_TICK}
                tickFormatter={(v) =>
                  truncate(String(v), Math.max(4, Math.floor((width - valueAxisWidth - 20) / labels.length / 6.2)))
                }
                axisLine={{ stroke: CHART.axis }}
                tickLine={false}
                interval={labels.length <= 16 ? 0 : "preserveStartEnd"}
              />
              <YAxis
                tick={AXIS_TICK}
                tickFormatter={(v) => formatShort(v, fmt)}
                width={valueAxisWidth}
                axisLine={false}
                tickLine={false}
              />
            </>
          )}
          {mode !== "print" && (
            <Tooltip
              cursor={{ fill: CHART.grid, opacity: 0.5 }}
              content={(p) => <ChartTooltip active={p.active} payload={p.payload} label={p.label} fmt={fmt} raw={!shape.keysAreColumns} />}
              isAnimationActive={false}
            />
          )}
          {shape.keys.map((k, i) => {
            const last = i === shape.keys.length - 1;
            const rounded = !stacked || last;
            const radius: [number, number, number, number] = !rounded
              ? [0, 0, 0, 0]
              : horizontal
                ? [0, 4, 4, 0]
                : [4, 4, 0, 0];
            return (
              <Bar
                key={k}
                dataKey={k}
                name={k}
                fill={colors[i]}
                stackId={stacked ? "s" : undefined}
                maxBarSize={horizontal ? 22 : 40}
                radius={radius}
                stroke={stacked ? CHART.surface : undefined}
                strokeWidth={stacked ? 1 : 0}
                isAnimationActive={animate}
              >
                {showLabels && (
                  <LabelList
                    dataKey={k}
                    position={horizontal ? "right" : "top"}
                    formatter={(v: unknown) => formatShort(v, fmt)}
                    style={{ fill: CHART.textSecondary, fontSize: 10 }}
                  />
                )}
              </Bar>
            );
          })}
        </BarChart>
      )}
    </ChartBox>
  );
}
