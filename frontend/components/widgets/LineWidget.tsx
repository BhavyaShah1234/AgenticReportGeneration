"use client";

import { Area, AreaChart, CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS_TICK, ChartBox, ChartTooltip, EmptyState, LegendRow, yAxisWidth } from "./ChartParts";
import { extraFlag, toCartesian, widgetFormat, type WidgetBodyProps } from "./chartData";
import { formatShort } from "./format";
import { CHART, seriesColor } from "./palette";

/** Shared renderer for line and area charts (multi-series via encoding.series or several y columns). */
export function LineLikeChart({ spec, data, mode, variant }: WidgetBodyProps & { variant: "line" | "area" }) {
  const shape = toCartesian(data);
  const fmt = widgetFormat(spec);
  const animate = mode !== "print";
  if (!shape.rows.length || !shape.keys.length) return <EmptyState />;

  const colors = shape.keys.map((k, i) => seriesColor(i, k, spec.options?.color));
  const legend =
    spec.options?.show_legend !== false ? (
      <LegendRow raw={!shape.keysAreColumns} items={shape.keys.map((k, i) => ({ name: k, color: colors[i] }))} />
    ) : null;
  const stacked = variant === "area" && extraFlag(spec, "stacked") === true;
  const maxVal = Math.max(
    ...shape.rows.map((r) =>
      stacked ? shape.keys.reduce((a, k) => a + (Number(r[k]) || 0), 0) : Math.max(...shape.keys.map((k) => Number(r[k]) || 0)),
    ),
  );
  const yWidth = yAxisWidth([formatShort(maxVal, fmt)]);
  const showDots = shape.rows.length <= 16;
  const common = {
    data: shape.rows,
    margin: { top: 8, right: 14, bottom: 0, left: 0 },
  };
  const axes = (
    <>
      <CartesianGrid stroke={CHART.grid} vertical={false} />
      <XAxis
        dataKey={shape.xKey}
        tick={AXIS_TICK}
        axisLine={{ stroke: CHART.axis }}
        tickLine={false}
        minTickGap={18}
      />
      <YAxis tick={AXIS_TICK} tickFormatter={(v) => formatShort(v, fmt)} width={yWidth} axisLine={false} tickLine={false} />
      {mode !== "print" && (
        <Tooltip
          cursor={{ stroke: CHART.axis, strokeWidth: 1 }}
          content={(p) => <ChartTooltip active={p.active} payload={p.payload} label={p.label} fmt={fmt} raw={!shape.keysAreColumns} />}
          isAnimationActive={false}
        />
      )}
    </>
  );

  return (
    <ChartBox legend={legend}>
      {({ width, height }) =>
        variant === "line" ? (
          <LineChart width={width} height={height} {...common}>
            {axes}
            {shape.keys.map((k, i) => (
              <Line
                key={k}
                type="monotone"
                dataKey={k}
                name={k}
                stroke={colors[i]}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                dot={showDots ? { r: 3.5, fill: colors[i], stroke: CHART.surface, strokeWidth: 2 } : false}
                activeDot={{ r: 5, stroke: CHART.surface, strokeWidth: 2 }}
                connectNulls
                isAnimationActive={animate}
              />
            ))}
          </LineChart>
        ) : (
          <AreaChart width={width} height={height} {...common}>
            {axes}
            {shape.keys.map((k, i) => (
              <Area
                key={k}
                type="monotone"
                dataKey={k}
                name={k}
                stroke={colors[i]}
                strokeWidth={2}
                fill={colors[i]}
                fillOpacity={stacked ? 0.35 : 0.1}
                stackId={stacked ? "s" : undefined}
                activeDot={{ r: 5, stroke: CHART.surface, strokeWidth: 2 }}
                connectNulls
                isAnimationActive={animate}
              />
            ))}
          </AreaChart>
        )
      }
    </ChartBox>
  );
}

export function LineWidget(props: WidgetBodyProps) {
  return <LineLikeChart {...props} variant="line" />;
}
