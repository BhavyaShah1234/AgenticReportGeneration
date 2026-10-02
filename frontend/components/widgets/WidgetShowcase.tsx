"use client";

// Dev-only gallery of every widget type with fixtures shaped like real V_SALES archetype output.
// Mount it from any page, e.g. `<WidgetShowcase mode="print" />`, to eyeball rendering.
import type { WidgetData, WidgetSpec, WidgetType } from "@/lib/types";
import { defaultWidgetOptions } from "./catalog";
import { WidgetRenderer, type RenderMode } from "./WidgetRenderer";

function spec(id: string, type: WidgetType, title: string, extra: Partial<WidgetSpec["options"]> = {}): WidgetSpec {
  return {
    id,
    type,
    title,
    filters: [],
    ignore_params: [],
    layout: { x: 0, y: 0, w: 6, h: 7 },
    options: { ...defaultWidgetOptions(type), ...extra },
  };
}

const n = (name: string) => ({ name, type: "number" as const });
const s = (name: string) => ({ name, type: "string" as const });
const d = (name: string) => ({ name, type: "date" as const });

const byLine: WidgetData = {
  widget_id: "bar",
  columns: [s("PRODUCT_LINE"), n("VALUE"), n("SHARE")],
  rows: [
    ["Classic Cars", 3919615.66, 0.3907],
    ["Vintage Cars", 1903150.84, 0.1897],
    ["Motorcycles", 1166388.34, 0.1163],
    ["Trucks and Buses", 1127789.84, 0.1124],
    ["Planes", 975003.57, 0.0972],
    ["Ships", 714437.13, 0.0712],
    ["Trains", 226243.47, 0.0226],
  ].map(([a, b, c]) => ({ PRODUCT_LINE: a, VALUE: b, SHARE: c })),
  encoding: { x: "PRODUCT_LINE", y: ["VALUE"], label: "PRODUCT_LINE", value: "VALUE" },
  meta: {},
};

const months = Array.from({ length: 17 }, (_, i) => {
  const dt = new Date(Date.UTC(2004, i, 1));
  return dt.toISOString().slice(0, 10);
});
const monthly: WidgetData = {
  widget_id: "line",
  columns: [d("ORDER_DATE"), n("VALUE"), n("MOVING_AVG")],
  rows: months.map((m, i) => {
    const v = 250000 + 180000 * Math.sin(i / 2) + (i % 11 === 10 ? 600000 : 0);
    return { ORDER_DATE: m, VALUE: Math.round(v), MOVING_AVG: Math.round(v * 0.9 + 30000) };
  }),
  encoding: { x: "ORDER_DATE", y: ["VALUE", "MOVING_AVG"] },
  meta: {},
};

const territories = ["EMEA", "NA", "APAC", "Japan"];
const longFormat: WidgetData = {
  widget_id: "area",
  columns: [d("ORDER_DATE"), s("TERRITORY"), n("VALUE")],
  rows: ["2003-01-01", "2003-04-01", "2003-07-01", "2003-10-01", "2004-01-01", "2004-04-01"].flatMap((q, i) =>
    territories.map((t, j) => ({ ORDER_DATE: q, TERRITORY: t, VALUE: (4 - j) * 90000 + i * 25000 * (j + 1) })),
  ),
  encoding: { x: "ORDER_DATE", y: ["VALUE"], series: "TERRITORY" },
  meta: {},
};

const pivot: WidgetData = {
  widget_id: "stacked",
  columns: [s("TERRITORY"), n("Classic Cars"), n("Vintage Cars"), n("Motorcycles")],
  rows: [
    { TERRITORY: "APAC", "Classic Cars": 244758, "Vintage Cars": 208852, Motorcycles: 89968 },
    { TERRITORY: "EMEA", "Classic Cars": 2086994, "Vintage Cars": 848981, Motorcycles: 503096 },
    { TERRITORY: "Japan", "Classic Cars": 142500, "Vintage Cars": 90450, Motorcycles: 70000 },
    { TERRITORY: "NA", "Classic Cars": 1445362, "Vintage Cars": 754867, Motorcycles: 503323 },
  ],
  encoding: { x: "TERRITORY", y: ["Classic Cars", "Vintage Cars", "Motorcycles"] },
  meta: {},
};

const kpi: WidgetData = {
  widget_id: "kpi",
  columns: [n("VALUE"), n("PREVIOUS")],
  rows: [{ VALUE: 375268.36, PREVIOUS: 210227.58 }],
  encoding: { value: "VALUE", y: ["VALUE"] },
  meta: { value: 375268.36, previous: 210227.58, delta_pct: 0.785, period_label: "2004", previous_label: "2003" },
};

const scatter: WidgetData = {
  widget_id: "scatter",
  columns: [s("CLIENT_NAME"), n("VALUE"), n("PREVIOUS"), n("CHANGE_PCT")],
  rows: Array.from({ length: 30 }, (_, i) => ({
    CLIENT_NAME: `Client ${i + 1}`,
    VALUE: 20000 + ((i * 7919) % 180000),
    PREVIOUS: 15000 + ((i * 6151) % 160000),
    CHANGE_PCT: 0.1,
  })),
  encoding: { x: "CLIENT_NAME", y: ["VALUE", "PREVIOUS"] },
  meta: {},
};

const ITEMS: { spec: WidgetSpec; data?: WidgetData; loading?: boolean; error?: string; h: number; w: number }[] = [
  { spec: spec("k1", "kpi", "Sales — Euro Shopping Channel"), data: kpi, w: 3, h: 3 },
  {
    spec: spec("k2", "kpi", "Returns", { format: "number", extra: { lower_is_better: true } }),
    data: { ...kpi, meta: { ...kpi.meta, value: 42, previous: 30, delta_pct: 0.4 } },
    w: 3,
    h: 3,
  },
  { spec: spec("k3", "kpi", "Loading KPI"), loading: true, w: 3, h: 3 },
  { spec: spec("k4", "kpi", "Broken KPI"), error: "Unknown column 'SALEZ'. Available: SALES, …", w: 3, h: 3 },
  { spec: spec("h1", "heading", "", { text: "Sales overview", extra: { subtitle: "Jan–Dec 2004" } }), w: 12, h: 2 },
  { spec: spec("b1", "bar", "Sales by product line"), data: byLine, w: 6, h: 7 },
  { spec: spec("b2", "bar", "Sales by product line (horizontal, labels)", { show_labels: true, extra: { horizontal: true } }), data: byLine, w: 6, h: 7 },
  { spec: spec("sb", "stacked_bar", "Territory × product line"), data: pivot, w: 6, h: 7 },
  { spec: spec("l1", "line", "Monthly sales vs 3-month average"), data: monthly, w: 6, h: 7 },
  { spec: spec("a1", "area", "Quarterly sales by territory"), data: longFormat, w: 6, h: 7 },
  { spec: spec("p1", "pie", "Share of sales"), data: byLine, w: 3, h: 7 },
  { spec: spec("p2", "donut", "Share of sales (donut)"), data: byLine, w: 3, h: 7 },
  { spec: spec("sc", "scatter", "This year vs last year, per client"), data: scatter, w: 6, h: 7 },
  { spec: spec("t1", "table", "Product lines"), data: byLine, w: 6, h: 7 },
  {
    spec: spec("x1", "text", "Summary", {
      text: "Sales grew **78%** year over year.\n\n- Classic Cars led with **49%** of sales\n- Q4 was the strongest quarter",
    }),
    w: 6,
    h: 4,
  },
  { spec: spec("x2", "text", "AI narrative", { narrative: true, text: null }), w: 6, h: 4 },
  { spec: spec("e1", "line", "No rows"), data: { ...monthly, rows: [] }, w: 6, h: 4 },
];

export function WidgetShowcase({ mode = "preview" }: { mode?: RenderMode }) {
  return (
    <div className="grid grid-cols-12 gap-3 bg-zinc-50 p-4" style={{ gridAutoRows: 40 }}>
      {ITEMS.map((it) => (
        <div key={it.spec.id} style={{ gridColumn: `span ${it.w}`, gridRow: `span ${it.h}` }}>
          <WidgetRenderer spec={it.spec} data={it.data} loading={it.loading} error={it.error} mode={mode} />
        </div>
      ))}
    </div>
  );
}
