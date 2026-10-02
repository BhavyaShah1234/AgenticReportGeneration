// STUB — the widgets agent completes this. Keep the exported shape stable.
import type { ArchetypeConfig, WidgetType } from "@/lib/types";

export interface WidgetCatalogEntry {
  type: WidgetType;
  label: string;
  /** lucide-react icon component name, e.g. "BarChart3" */
  icon: string;
  defaultSize: { w: number; h: number };
  /** false for heading / static text widgets */
  needsData: boolean;
  /** Archetype preselected when the widget is dropped on the canvas */
  defaultArchetype?: ArchetypeConfig;
}

export const WIDGET_CATALOG: WidgetCatalogEntry[] = [
  { type: "kpi", label: "KPI", icon: "Gauge", defaultSize: { w: 3, h: 4 }, needsData: true },
  { type: "bar", label: "Bar chart", icon: "BarChart3", defaultSize: { w: 6, h: 8 }, needsData: true },
  { type: "line", label: "Line chart", icon: "LineChart", defaultSize: { w: 6, h: 8 }, needsData: true },
  { type: "pie", label: "Pie chart", icon: "PieChart", defaultSize: { w: 4, h: 8 }, needsData: true },
  { type: "table", label: "Table", icon: "Table", defaultSize: { w: 12, h: 8 }, needsData: true },
  { type: "heading", label: "Heading", icon: "Heading", defaultSize: { w: 12, h: 2 }, needsData: false },
  { type: "text", label: "Text", icon: "Type", defaultSize: { w: 6, h: 4 }, needsData: false },
];
