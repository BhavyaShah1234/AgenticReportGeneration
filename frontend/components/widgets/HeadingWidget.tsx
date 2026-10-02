"use client";

import type { WidgetSpec } from "@/lib/types";

/** Section heading: options.text (or the title) with an optional options.extra.subtitle. */
export function HeadingWidget({ spec }: { spec: WidgetSpec }) {
  const text = spec.options?.text || spec.title || "Heading";
  const subtitle = typeof spec.options?.extra?.subtitle === "string" ? (spec.options.extra.subtitle as string) : null;
  return (
    <div className="flex h-full w-full flex-col justify-start px-1 pt-1">
      <div className="border-b border-zinc-200 pb-1.5">
      <h2 className="truncate text-lg font-semibold tracking-tight text-zinc-900">{text}</h2>
        {subtitle && <p className="truncate text-xs text-zinc-500">{subtitle}</p>}
      </div>
    </div>
  );
}
