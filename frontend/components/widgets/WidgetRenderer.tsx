"use client";

import { clsx } from "clsx";
import { AlertTriangle } from "lucide-react";
import type { WidgetData, WidgetSpec } from "@/lib/types";
import { AreaWidget } from "./AreaWidget";
import { BarWidget } from "./BarWidget";
import { EmptyState } from "./ChartParts";
import type { RenderMode } from "./chartData";
import { HeadingWidget } from "./HeadingWidget";
import { KpiWidget } from "./KpiWidget";
import { LineWidget } from "./LineWidget";
import { PieWidget } from "./PieWidget";
import { ScatterWidget } from "./ScatterWidget";
import { TableWidget } from "./TableWidget";
import { TextWidget } from "./TextWidget";

export type { RenderMode } from "./chartData";

export interface WidgetRendererProps {
  spec: WidgetSpec;
  data?: WidgetData | null;
  loading?: boolean;
  error?: string | null;
  /** print: no animations, no hover UI, fixed sizes friendly to PDF */
  mode?: RenderMode;
}

const TITLES: Record<string, string> = {
  kpi: "KPI",
  table: "Table",
  bar: "Bar chart",
  stacked_bar: "Stacked bar",
  line: "Line chart",
  area: "Area chart",
  pie: "Pie chart",
  donut: "Donut chart",
  scatter: "Scatter plot",
  text: "",
  heading: "",
};

function Skeleton({ type }: { type: WidgetSpec["type"] }) {
  if (type === "kpi")
    return (
      <div className="flex h-full flex-col justify-center gap-2 px-4 pb-3">
        <div className="h-8 w-2/3 animate-pulse rounded bg-zinc-100" />
        <div className="h-3 w-1/3 animate-pulse rounded bg-zinc-100" />
      </div>
    );
  return (
    <div className="flex h-full items-end gap-2 px-4 pb-4 pt-2" aria-label="Loading">
      {[55, 80, 40, 95, 65, 75, 35].map((h, i) => (
        <div key={i} className="flex-1 animate-pulse rounded-t bg-zinc-100" style={{ height: `${h}%` }} />
      ))}
    </div>
  );
}

function ErrorState({ message, mode }: { message: string; mode: RenderMode }) {
  return (
    <div className="flex h-full w-full items-center justify-center p-3">
      <div className="flex max-w-full items-start gap-2 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className={clsx("break-words", mode === "print" ? "line-clamp-2" : "line-clamp-6")} title={message}>
          {message}
        </span>
      </div>
    </div>
  );
}

function Body({ spec, data, mode }: { spec: WidgetSpec; data: WidgetData; mode: RenderMode }) {
  const props = { spec, data, mode };
  switch (spec.type) {
    case "kpi":
      return <KpiWidget {...props} />;
    case "bar":
    case "stacked_bar":
      return <BarWidget {...props} />;
    case "line":
      return <LineWidget {...props} />;
    case "area":
      return <AreaWidget {...props} />;
    case "pie":
    case "donut":
      return <PieWidget {...props} />;
    case "scatter":
      return <ScatterWidget {...props} />;
    case "table":
      return <TableWidget {...props} />;
    default:
      return <EmptyState message={`Unsupported widget type "${spec.type}"`} />;
  }
}

/**
 * Renders any widget inside a card that fills its parent (give the parent a size).
 * Handles loading / error / empty states; `mode="print"` disables animation and hover UI.
 */
export function WidgetRenderer({ spec, data, loading, error, mode = "preview" }: WidgetRendererProps) {
  const print = mode === "print";

  if (spec.type === "heading") {
    return (
      <div className={clsx("h-full w-full", print && "print-widget")}>
        <HeadingWidget spec={spec} />
      </div>
    );
  }

  const title = spec.title || TITLES[spec.type] || "";
  const err = error ?? data?.error ?? null;
  let body: React.ReactNode;
  if (spec.type === "text") {
    body = loading && spec.options?.narrative ? <Skeleton type="text" /> : <TextWidget spec={spec} data={data} mode={mode} />;
  } else if (loading) {
    body = <Skeleton type={spec.type} />;
  } else if (err) {
    body = <ErrorState message={err} mode={mode} />;
  } else if (!data) {
    body = <EmptyState message={mode === "design" ? "Configure an archetype to load data" : "No data"} />;
  } else if (!data.rows.length && spec.type !== "kpi") {
    body = <EmptyState />;
  } else {
    body = <Body spec={spec} data={data} mode={mode} />;
  }

  return (
    <div
      className={clsx(
        "flex h-full w-full flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white",
        print ? "print-widget" : "shadow-sm",
      )}
      data-widget-id={spec.id}
      data-widget-ready={!loading ? "true" : "false"}
    >
      {title && (
        <div className="flex shrink-0 items-center gap-2 px-3 pt-2.5 pb-1">
          <h3 className="truncate text-[13px] font-medium text-zinc-800" title={title}>
            {title}
          </h3>
        </div>
      )}
      <div className={clsx("min-h-0 flex-1", spec.type !== "table" && spec.type !== "kpi" && spec.type !== "text" && "px-2 pb-2")}>
        {body}
      </div>
    </div>
  );
}
