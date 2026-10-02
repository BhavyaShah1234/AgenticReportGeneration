// Turns WidgetData (+ Encoding) into the wide row shape recharts wants.
import type { ColumnInfo, WidgetData, WidgetSpec } from "@/lib/types";
import { MAX_SERIES } from "./palette";
import { datePatternFor, formatCategory, toNumber, type ValueFormat } from "./format";

export type RenderMode = "design" | "preview" | "print";

export interface WidgetBodyProps {
  spec: WidgetSpec;
  data: WidgetData;
  mode: RenderMode;
}

export interface CartesianShape {
  /** Key in each row holding the formatted category / date label */
  xKey: string;
  /** Numeric series keys, in palette order */
  keys: string[];
  rows: Record<string, unknown>[];
  /** true when x values are ISO dates */
  isTime: boolean;
  /** true when keys are column names (VALUE, MOVING_AVG) rather than data values (EMEA) */
  keysAreColumns: boolean;
}

export const X_LABEL = "__x";

function numericColumns(cols: ColumnInfo[]): string[] {
  return cols.filter((c) => c.type === "number").map((c) => c.name);
}

export function resolveX(data: WidgetData): string | undefined {
  const enc = data.encoding;
  if (enc?.x) return enc.x;
  if (enc?.label) return enc.label;
  const first = data.columns.find((c) => c.type !== "number") ?? data.columns[0];
  return first?.name;
}

export function resolveY(data: WidgetData, x?: string): string[] {
  const y = data.encoding?.y?.filter(Boolean) ?? [];
  if (y.length) return y;
  return numericColumns(data.columns).filter((c) => c !== x);
}

/**
 * Wide rows for bar/line/area. Long format (encoding.series) is pivoted client-side;
 * series beyond the palette fold into "Other" (summed) so hues are never cycled.
 */
export function toCartesian(data: WidgetData): CartesianShape {
  const x = resolveX(data);
  const ys = resolveY(data, x);
  const series = data.encoding?.series;
  const isTime = x ? data.rows.some((r) => typeof r[x] === "string" && /^\d{4}-\d{2}-\d{2}/.test(r[x] as string)) : false;
  const pattern = isTime && x ? datePatternFor(data.rows.map((r) => r[x])) : undefined;

  if (!x) return { xKey: X_LABEL, keys: [], rows: [], isTime: false, keysAreColumns: true };

  if (series && ys.length) {
    const v = ys[0];
    const totals = new Map<string, number>();
    for (const r of data.rows) {
      const s = r[series] === null || r[series] === undefined ? "(blank)" : String(r[series]);
      totals.set(s, (totals.get(s) ?? 0) + Math.abs(toNumber(r[v]) ?? 0));
    }
    const ranked = [...totals.entries()].sort((a, b) => b[1] - a[1]).map(([s]) => s);
    const keep = ranked.length > MAX_SERIES ? ranked.slice(0, MAX_SERIES - 1) : ranked;
    const keepSet = new Set(keep);
    const keys = ranked.length > keep.length ? [...keep, "Other"] : keep;
    const byX = new Map<string, Record<string, unknown>>();
    const order: string[] = [];
    for (const r of data.rows) {
      const xv = String(r[x] ?? "");
      let row = byX.get(xv);
      if (!row) {
        row = { [X_LABEL]: formatCategory(r[x], pattern), __raw: r[x] };
        byX.set(xv, row);
        order.push(xv);
      }
      const s = r[series] === null || r[series] === undefined ? "(blank)" : String(r[series]);
      const k = keepSet.has(s) ? s : "Other";
      const n = toNumber(r[v]);
      if (n !== null) row[k] = ((row[k] as number | undefined) ?? 0) + n;
    }
    if (isTime) order.sort();
    return { xKey: X_LABEL, keys, rows: order.map((k) => byX.get(k)!), isTime, keysAreColumns: false };
  }

  const keys = ys.slice(0, MAX_SERIES);
  const rows = data.rows.map((r) => {
    const out: Record<string, unknown> = { [X_LABEL]: formatCategory(r[x], pattern), __raw: r[x] };
    for (const k of keys) out[k] = toNumber(r[k]);
    return out;
  });
  // pivot output uses data values as column names (mixed case), humanize() leaves those alone
  return { xKey: X_LABEL, keys, rows, isTime, keysAreColumns: true };
}

export interface Slice {
  name: string;
  value: number;
}

/** label/value pairs for pie & donut; keeps the largest slices and folds the rest. */
export function toSlices(data: WidgetData, max = MAX_SERIES): Slice[] {
  const label = data.encoding?.label ?? resolveX(data);
  const value = data.encoding?.value ?? resolveY(data, label)[0];
  if (!label || !value) return [];
  const pattern = datePatternFor(data.rows.map((r) => r[label]));
  const slices = data.rows
    .map((r) => ({ name: formatCategory(r[label], pattern), value: toNumber(r[value]) ?? 0 }))
    .filter((s) => s.value > 0);
  const other = slices.filter((s) => s.name === "Other");
  const rest = slices.filter((s) => s.name !== "Other").sort((a, b) => b.value - a.value);
  const keep = rest.slice(0, max - 1);
  const folded = rest.slice(max - 1).reduce((a, s) => a + s.value, 0) + other.reduce((a, s) => a + s.value, 0);
  return folded > 0 ? [...keep, { name: "Other", value: folded }] : keep;
}

export function widgetFormat(spec: WidgetSpec): ValueFormat {
  return (spec.options?.format as ValueFormat) ?? "number";
}

export function extraFlag(spec: WidgetSpec, key: string): boolean | undefined {
  const v = spec.options?.extra?.[key];
  return typeof v === "boolean" ? v : undefined;
}
