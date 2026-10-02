"use client";

import { useState } from "react";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import type { DateRange } from "@/lib/types";
import { cn } from "@/lib/utils";
import { DATE_PRESETS, presetFor } from "./presets";

export function DateRangeInput({
  value,
  onChange,
  size = "md",
  showDates = true,
  className,
}: {
  value: DateRange | null | undefined;
  onChange: (v: DateRange | null) => void;
  size?: "sm" | "md";
  showDates?: boolean | "custom";
  className?: string;
}) {
  const [customMode, setCustomMode] = useState(false);
  const preset = customMode ? undefined : presetFor(value);
  const custom = !!value && !preset;
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <Select
        selectSize={size}
        className="w-36"
        value={preset?.key ?? (value ? "custom" : "")}
        onValueChange={(k) => {
          if (k === "custom") {
            setCustomMode(true);
            onChange(value ?? { ...DATE_PRESETS[0].range });
            return;
          }
          setCustomMode(false);
          const p = DATE_PRESETS.find((x) => x.key === k);
          onChange(p ? { ...p.range } : null);
        }}
      >
        <option value="">Any period</option>
        {DATE_PRESETS.map((p) => (
          <option key={p.key} value={p.key}>
            {p.label}
          </option>
        ))}
        <option value="custom">Custom…</option>
      </Select>
      {value && (showDates === true || (showDates === "custom" && custom)) && (
        <div className="flex items-center gap-1.5">
          <Input
            type="date"
            inputSize={size}
            className="w-36"
            value={value.start}
            max={value.end}
            onChange={(e) => onChange({ ...value, start: e.target.value })}
          />
          <span className="text-xs text-zinc-400">to</span>
          <Input
            type="date"
            inputSize={size}
            className="w-36"
            value={value.end}
            min={value.start}
            onChange={(e) => onChange({ ...value, end: e.target.value })}
          />
        </div>
      )}
    </div>
  );
}
