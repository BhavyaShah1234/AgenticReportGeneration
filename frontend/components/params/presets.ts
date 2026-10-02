import type { DateRange, ParamDef, ParamValue, ParamValues } from "@/lib/types";

/** Demo dataset spans 2003-01-06 .. 2005-05-31. */
export const DATA_START = "2003-01-01";
export const DATA_END = "2005-05-31";

export interface DatePreset {
  key: string;
  label: string;
  range: DateRange;
}

export const DATE_PRESETS: DatePreset[] = [
  { key: "all", label: "All time", range: { start: DATA_START, end: DATA_END } },
  { key: "2003", label: "2003", range: { start: "2003-01-01", end: "2003-12-31" } },
  { key: "2004", label: "2004", range: { start: "2004-01-01", end: "2004-12-31" } },
  { key: "2005", label: "2005 (YTD)", range: { start: "2005-01-01", end: "2005-05-31" } },
  { key: "q1-2004", label: "Q1 2004", range: { start: "2004-01-01", end: "2004-03-31" } },
  { key: "q2-2004", label: "Q2 2004", range: { start: "2004-04-01", end: "2004-06-30" } },
  { key: "q3-2004", label: "Q3 2004", range: { start: "2004-07-01", end: "2004-09-30" } },
  { key: "q4-2004", label: "Q4 2004", range: { start: "2004-10-01", end: "2004-12-31" } },
  { key: "q1-2005", label: "Q1 2005", range: { start: "2005-01-01", end: "2005-03-31" } },
];

export function presetFor(range: DateRange | null | undefined): DatePreset | undefined {
  if (!range) return undefined;
  return DATE_PRESETS.find((p) => p.range.start === range.start && p.range.end === range.end);
}

export function isDateRange(v: unknown): v is DateRange {
  return !!v && typeof v === "object" && "start" in v && "end" in v;
}

export function formatParamValue(v: ParamValue | unknown): string {
  if (v == null || v === "") return "—";
  if (isDateRange(v)) return presetFor(v)?.label ?? `${v.start} → ${v.end}`;
  return String(v);
}

/** Initial values for a set of ParamDefs (respecting `default`). */
export function defaultValues(params: ParamDef[], clientScope?: string | null): ParamValues {
  const out: ParamValues = {};
  for (const p of params) {
    if (p.default != null) out[p.name] = p.default as ParamValue;
    else if (p.type === "date_range") out[p.name] = { ...DATE_PRESETS[0].range };
    else if (p.type === "client" && clientScope) out[p.name] = clientScope;
  }
  return out;
}

/** Drop empty values so the backend treats them as "not provided". */
export function cleanValues(values: ParamValues): ParamValues {
  const out: ParamValues = {};
  for (const [k, v] of Object.entries(values)) {
    if (v == null || v === "") continue;
    out[k] = v;
  }
  return out;
}

export const PARAM_PRESETS: Record<"client" | "period", ParamDef> = {
  client: { name: "client", label: "Client", type: "client", column: "CLIENT_NAME", required: true },
  period: { name: "period", label: "Period", type: "date_range", column: "ORDER_DATE", required: true },
};
