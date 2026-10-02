import { createElement } from "react";
import {
  AreaChart,
  BarChart3,
  ChartArea,
  ChartBar,
  ChartColumn,
  ChartColumnStacked,
  ChartLine,
  ChartPie,
  ChartScatter,
  Donut,
  Gauge,
  Hash,
  Heading,
  Heading1,
  LineChart,
  PieChart,
  ScatterChart,
  Shapes,
  Table,
  Table2,
  Text,
  Type,
  type LucideIcon,
} from "lucide-react";
import { catalogEntry } from "@/lib/stores/designer";
import type { ArchetypeConfig, ArchetypeSpec, WidgetType } from "@/lib/types";

const ICONS: Record<string, LucideIcon> = {
  AreaChart,
  BarChart3,
  ChartArea,
  ChartBar,
  ChartColumn,
  ChartColumnStacked,
  ChartLine,
  ChartPie,
  ChartScatter,
  Donut,
  Gauge,
  Hash,
  Heading,
  Heading1,
  LineChart,
  PieChart,
  ScatterChart,
  Table,
  Table2,
  Text,
  Type,
};

const TYPE_ICONS: Record<WidgetType, LucideIcon> = {
  kpi: Gauge,
  table: Table,
  bar: BarChart3,
  stacked_bar: ChartColumnStacked,
  line: LineChart,
  area: AreaChart,
  pie: PieChart,
  donut: Donut,
  scatter: ScatterChart,
  text: Type,
  heading: Heading,
};

export function iconFor(type: WidgetType, iconName?: string): LucideIcon {
  return (iconName && ICONS[iconName]) || TYPE_ICONS[type] || Shapes;
}

export function WidgetIcon({ type, className }: { type: WidgetType; className?: string }) {
  return createElement(iconFor(type, catalogEntry(type)?.icon), { className });
}

export const TYPE_LABELS: Record<WidgetType, string> = {
  kpi: "KPI",
  table: "Table",
  bar: "Bar chart",
  stacked_bar: "Stacked bar",
  line: "Line chart",
  area: "Area chart",
  pie: "Pie chart",
  donut: "Donut chart",
  scatter: "Scatter plot",
  text: "Text",
  heading: "Heading",
};

export function typeLabel(type: WidgetType) {
  return catalogEntry(type)?.label ?? TYPE_LABELS[type] ?? type;
}

const COMPAT_GROUPS: WidgetType[][] = [
  ["bar", "stacked_bar", "line", "area", "scatter", "table"],
  ["pie", "donut", "bar", "table"],
  ["kpi", "table"],
  ["text", "heading"],
];

/** Widget types a widget can switch to without losing its data shape. */
export function compatibleTypes(type: WidgetType): WidgetType[] {
  const out = new Set<WidgetType>([type]);
  for (const g of COMPAT_GROUPS) if (g.includes(type)) g.forEach((t) => out.add(t));
  if (type === "table") ["bar", "line", "area", "pie", "donut", "kpi", "stacked_bar", "scatter"].forEach((t) => out.add(t as WidgetType));
  return [...out];
}

const FALLBACK_ARCHETYPE: Partial<Record<WidgetType, string>> = {
  kpi: "kpi_summary",
  line: "time_series",
  area: "time_series",
  bar: "aggregate",
  stacked_bar: "aggregate",
  pie: "share_of_total",
  donut: "share_of_total",
  table: "aggregate",
  scatter: "aggregate",
};

/** Archetype preselected for a new widget of `type`. */
export function defaultArchetypeFor(type: WidgetType, archetypes: ArchetypeSpec[] | undefined): ArchetypeConfig | null {
  const entry = catalogEntry(type);
  if (entry && !entry.needsData) return null;
  if (entry?.defaultArchetype) return structuredClone(entry.defaultArchetype);
  if (!archetypes?.length) {
    const id = FALLBACK_ARCHETYPE[type];
    return id ? { id, params: {} } : null;
  }
  const preferred = FALLBACK_ARCHETYPE[type];
  const spec =
    archetypes.find((a) => a.id === preferred) ??
    archetypes.find((a) => a.kind === "builtin" && a.suggested_widgets.includes(type));
  return spec ? { id: spec.id, params: structuredClone(spec.example_params ?? {}) } : null;
}

/** Drag payload for palette → canvas drops (dataTransfer is unreadable during dragover). */
export interface PaletteDrag {
  type: WidgetType;
  archetype?: ArchetypeConfig | null;
  title?: string;
}
const paletteDrag: { current: PaletteDrag | null } = { current: null };
export function setPaletteDrag(v: PaletteDrag | null) {
  paletteDrag.current = v;
}
export function getPaletteDrag() {
  return paletteDrag.current;
}
