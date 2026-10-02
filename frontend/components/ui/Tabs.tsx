"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface TabItem<T extends string> {
  value: T;
  label: ReactNode;
}

/** Segmented-control style tabs (controlled). */
export function Tabs<T extends string>({
  value,
  onChange,
  items,
  className,
  size = "md",
}: {
  value: T;
  onChange: (v: T) => void;
  items: TabItem<T>[];
  className?: string;
  size?: "sm" | "md";
}) {
  return (
    <div role="tablist" className={cn("inline-flex rounded-lg bg-zinc-100 p-0.5", className)}>
      {items.map((it) => (
        <button
          key={it.value}
          type="button"
          role="tab"
          aria-selected={value === it.value}
          onClick={() => onChange(it.value)}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md font-medium whitespace-nowrap transition-colors",
            size === "sm" ? "px-2 py-1 text-xs" : "px-3 py-1.5 text-sm",
            value === it.value ? "bg-white text-zinc-900 shadow-xs" : "text-zinc-500 hover:text-zinc-800",
          )}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}
