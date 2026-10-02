"use client";

import { Combobox } from "@/components/ui/Combobox";
import { Input } from "@/components/ui/Input";
import { schemaApi } from "@/lib/endpoints";
import { useQuery } from "@/lib/hooks";
import type { DateRange, ParamDef, ParamValue } from "@/lib/types";
import { DateRangeInput } from "./DateRangeInput";
import { isDateRange } from "./presets";

/** Distinct values of a column (cached), for client / select dropdowns. */
export function useColumnValues(table: string | null | undefined, column: string | null | undefined) {
  const key = table && column ? `values:${table}:${column}` : null;
  const q = useQuery(key, () => schemaApi.values(table!, column!));
  const options = (q.data ?? []).filter((v) => v != null).map((v) => String(v));
  return { ...q, options };
}

/** Input control for one runtime parameter value, chosen by ParamDef.type. */
export function ParamValueInput({
  def,
  table,
  value,
  onChange,
  size = "md",
  showDates = true,
  anyLabel,
}: {
  def: ParamDef;
  table: string | null | undefined;
  value: ParamValue;
  onChange: (v: ParamValue) => void;
  size?: "sm" | "md";
  showDates?: boolean | "custom";
  anyLabel?: string;
}) {
  const needsValues = def.type === "client" || def.type === "select";
  const valuesColumn = needsValues ? def.options_column || def.column : null;
  const { options, loading, error } = useColumnValues(needsValues ? table : null, valuesColumn);

  switch (def.type) {
    case "date_range":
      return (
        <DateRangeInput
          size={size}
          showDates={showDates}
          value={isDateRange(value) ? (value as DateRange) : null}
          onChange={(v) => onChange(v)}
        />
      );
    case "client":
    case "select":
      if (!valuesColumn) {
        return (
          <Input
            inputSize={size}
            value={(value as string) ?? ""}
            placeholder={anyLabel ?? def.label}
            onChange={(e) => onChange(e.target.value || null)}
          />
        );
      }
      return (
        <Combobox
          size={size}
          value={(value as string) ?? null}
          onChange={(v) => onChange(v)}
          options={options}
          loading={loading}
          placeholder={error ? "Could not load values" : (anyLabel ?? `Select ${def.label.toLowerCase()}…`)}
        />
      );
    case "number":
      return (
        <Input
          type="number"
          inputSize={size}
          value={value == null ? "" : String(value)}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        />
      );
    default:
      return (
        <Input
          inputSize={size}
          value={(value as string) ?? ""}
          placeholder={anyLabel}
          onChange={(e) => onChange(e.target.value || null)}
        />
      );
  }
}
