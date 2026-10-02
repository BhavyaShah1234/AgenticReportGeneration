"use client";

// STUB — replaced by the widgets agent. Keep the exported signature stable.
import type { ArchetypeSpec, ColumnInfo } from "@/lib/types";

export interface ArchetypeParamsFormProps {
  spec: ArchetypeSpec;
  /** Columns of the widget's data source, used for column pickers */
  columns: ColumnInfo[];
  value: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
}

export function ArchetypeParamsForm({ value, onChange }: ArchetypeParamsFormProps) {
  return (
    <textarea
      className="h-40 w-full rounded border p-2 font-mono text-xs"
      defaultValue={JSON.stringify(value, null, 2)}
      onBlur={(e) => {
        try {
          onChange(JSON.parse(e.target.value));
        } catch {}
      }}
    />
  );
}
