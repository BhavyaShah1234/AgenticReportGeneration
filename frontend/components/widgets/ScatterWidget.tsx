"use client";

import { CartesianGrid, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS_TICK, ChartBox, EmptyState, yAxisWidth } from "./ChartParts";
import { resolveX, resolveY, widgetFormat, type WidgetBodyProps } from "./chartData";
import { formatShort, formatValue, humanize, toNumber } from "./format";
import { CHART, seriesColor } from "./palette";

interface Point {
  x: number;
  y: number;
  label?: string;
}

/**
 * Scatter: x = encoding.x and y = encoding.y[0] when x is numeric. When x is a category
 * (e.g. CLIENT_NAME), the first two numeric columns become the axes and x labels each point.
 */
export function ScatterWidget({ spec, data, mode }: WidgetBodyProps) {
  const fmt = widgetFormat(spec);
  const x = resolveX(data);
  const numeric = data.columns.filter((c) => c.type === "number").map((c) => c.name);
  const xIsNum = !!x && numeric.includes(x);
  let xKey: string | undefined;
  let yKey: string | undefined;
  let labelKey: string | undefined;
  if (xIsNum) {
    xKey = x;
    yKey = resolveY(data, x)[0];
  } else {
    const ys = resolveY(data, x);
    const nums = [...ys, ...numeric.filter((n) => !ys.includes(n))];
    [xKey, yKey] = nums;
    labelKey = x;
  }
  const points: Point[] = [];
  if (xKey && yKey) {
    for (const r of data.rows) {
      const px = toNumber(r[xKey]);
      const py = toNumber(r[yKey]);
      if (px !== null && py !== null) points.push({ x: px, y: py, label: labelKey ? String(r[labelKey] ?? "") : undefined });
    }
  }
  if (!points.length || !xKey || !yKey) return <EmptyState message="Scatter needs two numeric columns" />;
  const color = seriesColor(0, undefined, spec.options?.color);
  const maxY = Math.max(...points.map((p) => p.y));

  return (
    <ChartBox>
      {({ width, height }) => (
        <ScatterChart width={width} height={height} margin={{ top: 8, right: 14, bottom: 14, left: 0 }}>
          <CartesianGrid stroke={CHART.grid} />
          <XAxis
            type="number"
            dataKey="x"
            name={humanize(xKey!)}
            tick={AXIS_TICK}
            tickFormatter={(v) => formatShort(v, "number")}
            axisLine={{ stroke: CHART.axis }}
            tickLine={false}
            label={{ value: humanize(xKey!), position: "insideBottom", offset: -8, fill: CHART.muted, fontSize: 11 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name={humanize(yKey!)}
            tick={AXIS_TICK}
            tickFormatter={(v) => formatShort(v, fmt)}
            width={yAxisWidth([formatShort(maxY, fmt)])}
            axisLine={false}
            tickLine={false}
          />
          {mode !== "print" && (
            <Tooltip
              cursor={{ strokeDasharray: "0", stroke: CHART.axis }}
              isAnimationActive={false}
              content={({ active, payload }) => {
                const p = active && payload?.[0]?.payload ? (payload[0].payload as Point) : null;
                if (!p) return null;
                return (
                  <div className="rounded-md border border-zinc-200 bg-white/95 px-2.5 py-2 text-xs shadow-md">
                    {p.label && <div className="mb-1 font-medium text-zinc-900">{p.label}</div>}
                    <div className="text-zinc-600">
                      {humanize(xKey!)}: <span className="font-medium text-zinc-900">{formatValue(p.x)}</span>
                    </div>
                    <div className="text-zinc-600">
                      {humanize(yKey!)}: <span className="font-medium text-zinc-900">{formatValue(p.y, fmt)}</span>
                    </div>
                  </div>
                );
              }}
            />
          )}
          <Scatter
            data={points}
            fill={color}
            fillOpacity={0.8}
            stroke={CHART.surface}
            strokeWidth={1.5}
            isAnimationActive={mode !== "print"}
          />
        </ScatterChart>
      )}
    </ChartBox>
  );
}
