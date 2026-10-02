// Widget palette for the designer: every WidgetType with default size + archetype.
// Sizes are on a 12-column react-grid-layout canvas with ~40px rows.
import type { ArchetypeConfig, WidgetOptions, WidgetType } from "@/lib/types";

export interface WidgetCatalogEntry {
  type: WidgetType;
  label: string;
  /** lucide-react icon component name, e.g. "BarChart3" */
  icon: string;
  /** One-line hint for the palette tooltip */
  description: string;
  defaultSize: { w: number; h: number };
  /** Smallest sensible size (react-grid-layout minW/minH) */
  minSize: { w: number; h: number };
  /** false for heading / static text widgets */
  needsData: boolean;
  /** Archetype preselected when the widget is dropped on the canvas */
  defaultArchetype?: ArchetypeConfig;
  /** Presentation defaults merged into WidgetSpec.options */
  defaultOptions?: Partial<WidgetOptions>;
  /** Archetype ids that produce a sensible shape for this widget (for filtering the picker) */
  compatibleArchetypes: string[];
}

const TIME = ["time_series", "moving_average", "period_over_period"];
const CATEGORY = ["aggregate", "top_n", "share_of_total", "pivot", "distribution", "period_over_period"];

export const WIDGET_CATALOG: WidgetCatalogEntry[] = [
  {
    type: "kpi",
    label: "KPI",
    icon: "Gauge",
    description: "One headline number with change vs the previous period",
    defaultSize: { w: 3, h: 3 },
    minSize: { w: 2, h: 3 },
    needsData: true,
    defaultArchetype: { id: "kpi_summary", params: { measure: "SALES", agg: "sum", date_column: "ORDER_DATE", compare: "previous_period" } },
    defaultOptions: { format: "currency" },
    compatibleArchetypes: ["kpi_summary"],
  },
  {
    type: "bar",
    label: "Bar chart",
    icon: "BarChart3",
    description: "Compare a measure across categories",
    defaultSize: { w: 6, h: 7 },
    minSize: { w: 3, h: 4 },
    needsData: true,
    defaultArchetype: { id: "aggregate", params: { dimensions: ["PRODUCT_LINE"], measure: "SALES", agg: "sum", sort: "desc" } },
    defaultOptions: { format: "currency" },
    compatibleArchetypes: [...CATEGORY, ...TIME],
  },
  {
    type: "stacked_bar",
    label: "Stacked bar",
    icon: "ChartColumnStacked",
    description: "Category totals split into parts",
    defaultSize: { w: 6, h: 7 },
    minSize: { w: 3, h: 4 },
    needsData: true,
    defaultArchetype: {
      id: "pivot",
      params: { row_dimension: "TERRITORY", column_dimension: "PRODUCT_LINE", measure: "SALES", agg: "sum", max_columns: 8 },
    },
    defaultOptions: { format: "currency" },
    compatibleArchetypes: ["pivot", "aggregate", "time_series"],
  },
  {
    type: "line",
    label: "Line chart",
    icon: "LineChart",
    description: "A trend over time",
    defaultSize: { w: 6, h: 7 },
    minSize: { w: 3, h: 4 },
    needsData: true,
    defaultArchetype: { id: "time_series", params: { date_column: "ORDER_DATE", measure: "SALES", agg: "sum", grain: "month" } },
    defaultOptions: { format: "currency" },
    compatibleArchetypes: TIME,
  },
  {
    type: "area",
    label: "Area chart",
    icon: "AreaChart",
    description: "A trend over time, emphasising volume",
    defaultSize: { w: 6, h: 7 },
    minSize: { w: 3, h: 4 },
    needsData: true,
    defaultArchetype: {
      id: "time_series",
      params: { date_column: "ORDER_DATE", measure: "SALES", agg: "sum", grain: "month", cumulative: true },
    },
    defaultOptions: { format: "currency" },
    compatibleArchetypes: TIME,
  },
  {
    type: "pie",
    label: "Pie chart",
    icon: "PieChart",
    description: "Share of a total across a few categories",
    defaultSize: { w: 4, h: 7 },
    minSize: { w: 3, h: 5 },
    needsData: true,
    defaultArchetype: { id: "share_of_total", params: { dimension: "PRODUCT_LINE", measure: "SALES", agg: "sum", top_k: 6 } },
    defaultOptions: { format: "currency" },
    compatibleArchetypes: ["share_of_total", "aggregate", "top_n"],
  },
  {
    type: "donut",
    label: "Donut chart",
    icon: "Donut",
    description: "Share of a total with the total in the middle",
    defaultSize: { w: 4, h: 7 },
    minSize: { w: 3, h: 5 },
    needsData: true,
    defaultArchetype: { id: "share_of_total", params: { dimension: "TERRITORY", measure: "SALES", agg: "sum", top_k: 6 } },
    defaultOptions: { format: "currency" },
    compatibleArchetypes: ["share_of_total", "aggregate", "top_n"],
  },
  {
    type: "scatter",
    label: "Scatter plot",
    icon: "ScatterChart",
    description: "Relationship between two numeric measures (e.g. this period vs last, per client)",
    defaultSize: { w: 6, h: 7 },
    minSize: { w: 3, h: 4 },
    needsData: true,
    // period_over_period per client gives two numeric columns: this year (VALUE) vs last (PREVIOUS)
    defaultArchetype: {
      id: "period_over_period",
      params: { date_column: "ORDER_DATE", measure: "SALES", agg: "sum", grain: "year", dimension: "CLIENT_NAME" },
    },
    defaultOptions: { format: "currency" },
    compatibleArchetypes: ["period_over_period", "pivot", "moving_average"],
  },
  {
    type: "table",
    label: "Table",
    icon: "Table",
    description: "Exact values in rows and columns",
    defaultSize: { w: 6, h: 8 },
    minSize: { w: 3, h: 3 },
    needsData: true,
    defaultArchetype: { id: "top_n", params: { dimension: "PRODUCT_LINE", measure: "SALES", agg: "sum", n: 10 } },
    defaultOptions: { format: "currency" },
    compatibleArchetypes: [...CATEGORY, ...TIME, "kpi_summary"],
  },
  {
    type: "heading",
    label: "Heading",
    icon: "Heading",
    description: "Section title",
    defaultSize: { w: 12, h: 2 },
    minSize: { w: 2, h: 1 },
    needsData: false,
    defaultOptions: { text: "Section title" },
    compatibleArchetypes: [],
  },
  {
    type: "text",
    label: "Text",
    icon: "Type",
    description: "Notes, or an AI-written narrative of the report's data",
    defaultSize: { w: 6, h: 4 },
    minSize: { w: 2, h: 2 },
    needsData: false,
    defaultOptions: { text: "Write a note here. Supports **bold** and - bullet lists." },
    compatibleArchetypes: [],
  },
];

export const WIDGET_CATALOG_BY_TYPE: Record<WidgetType, WidgetCatalogEntry> = Object.fromEntries(
  WIDGET_CATALOG.map((e) => [e.type, e]),
) as Record<WidgetType, WidgetCatalogEntry>;

export function catalogEntry(type: WidgetType): WidgetCatalogEntry {
  return WIDGET_CATALOG_BY_TYPE[type];
}

/** Full WidgetOptions with catalog defaults applied. */
export function defaultWidgetOptions(type: WidgetType): WidgetOptions {
  return {
    format: "number",
    show_legend: true,
    show_labels: false,
    narrative: false,
    extra: {},
    ...(WIDGET_CATALOG_BY_TYPE[type]?.defaultOptions ?? {}),
  };
}
