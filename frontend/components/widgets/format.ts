// Shared value formatting for widgets. `ValueFormat` mirrors WidgetOptions.format.
import { format as formatDate, isValid, parseISO } from "date-fns";

export type ValueFormat = "number" | "currency" | "percent" | "compact";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}(T.*)?$/;

export function toNumber(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

const cache = new Map<string, Intl.NumberFormat>();
function nf(key: string, opts: Intl.NumberFormatOptions): Intl.NumberFormat {
  let f = cache.get(key);
  if (!f) {
    f = new Intl.NumberFormat("en-US", opts);
    cache.set(key, f);
  }
  return f;
}

/** Full-precision-ish display, e.g. tables and tooltips. */
export function formatValue(v: unknown, fmt: ValueFormat = "number"): string {
  const n = toNumber(v);
  if (n === null) return v === null || v === undefined ? "—" : String(v);
  switch (fmt) {
    case "currency":
      return nf("cur", { style: "currency", currency: "USD", maximumFractionDigits: Math.abs(n) >= 1000 ? 0 : 2 }).format(n);
    case "percent":
      return nf("pct", { style: "percent", maximumFractionDigits: 1 }).format(n);
    case "compact":
      return nf("cmp", { notation: "compact", maximumFractionDigits: 1 }).format(n);
    default:
      return nf("num", { maximumFractionDigits: Math.abs(n) >= 100 ? 0 : 2 }).format(n);
  }
}

/** Short display for axes, KPI tiles and labels: 1.2K, $4.2M, 12%. */
export function formatShort(v: unknown, fmt: ValueFormat = "number"): string {
  const n = toNumber(v);
  if (n === null) return v === null || v === undefined ? "—" : String(v);
  if (fmt === "percent") return nf("pct0", { style: "percent", maximumFractionDigits: 1 }).format(n);
  if (fmt === "currency")
    return nf("curc", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(n);
  if (Math.abs(n) < 1000) return nf("small", { maximumFractionDigits: Math.abs(n) < 10 ? 2 : 0 }).format(n);
  return nf("cmp", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

export function formatPercentDelta(v: unknown): string {
  const n = toNumber(v);
  if (n === null) return "—";
  const s = nf("pctd", { style: "percent", maximumFractionDigits: 1 }).format(Math.abs(n));
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${s}`;
}

export function isIsoDate(v: unknown): v is string {
  return typeof v === "string" && ISO_DATE.test(v);
}

/** Pick a date pattern that suits a set of ISO dates (year / month / day buckets). */
export function datePatternFor(values: unknown[]): string {
  const ds = values.filter(isIsoDate);
  if (!ds.length) return "MMM d, yyyy";
  if (ds.every((d) => d.slice(5, 10) === "01-01")) return "yyyy";
  if (ds.every((d) => d.slice(8, 10) === "01")) return "MMM yyyy";
  return "MMM d, yyyy";
}

export function formatDateValue(v: unknown, pattern = "MMM d, yyyy"): string {
  if (!isIsoDate(v)) return v === null || v === undefined ? "—" : String(v);
  const d = parseISO(v);
  return isValid(d) ? formatDate(d, pattern) : v;
}

/** Category/axis label: dates get formatted, everything else stringified. */
export function formatCategory(v: unknown, datePattern?: string): string {
  if (v === null || v === undefined) return "(blank)";
  if (isIsoDate(v)) return formatDateValue(v, datePattern);
  return String(v);
}

/** "PRODUCT_LINE" -> "Product line"; leaves mixed-case names (pivot values) alone. */
export function humanize(name: string): string {
  if (name !== name.toUpperCase()) return name;
  // short all-caps tokens are usually acronyms in the data (NA, EMEA, USA), not column names
  if (!name.includes("_") && name.length < 5) return name;
  const s = name.toLowerCase().replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1).replace(/\bpct\b/, "%");
}

/** Columns that hold ratios render as percents regardless of the widget format. */
export function isRatioColumn(name: string): boolean {
  return /(^|_)(SHARE|PCT|PERCENT|RATE|RATIO)($|_)/i.test(name);
}

/** Columns that hold counts never get a currency format. */
export function isCountColumn(name: string): boolean {
  return /(^|_)(COUNT|CNT|NUM|ORDERS)($|_)/i.test(name);
}

export function formatForColumn(name: string, fmt: ValueFormat): ValueFormat {
  if (isRatioColumn(name)) return "percent";
  if (isCountColumn(name) && fmt === "currency") return "number";
  return fmt;
}
