"use client";

// STUB — replaced by the widgets agent. Keep the exported signature stable.
import type { WidgetData, WidgetSpec } from "@/lib/types";

export type RenderMode = "design" | "preview" | "print";

export interface WidgetRendererProps {
  spec: WidgetSpec;
  data?: WidgetData | null;
  loading?: boolean;
  error?: string | null;
  /** print: no animations, no hover UI, fixed sizes friendly to PDF */
  mode?: RenderMode;
}

export function WidgetRenderer({ spec, data, loading, error }: WidgetRendererProps) {
  return (
    <div className="h-full w-full p-3 text-sm text-zinc-500">
      <div className="font-medium text-zinc-800">{spec.title || spec.type}</div>
      {loading ? "Loading…" : error ?? data?.error ?? `${data?.rows.length ?? 0} rows`}
    </div>
  );
}
