// Chart palette: validated categorical order (dataviz reference palette, light surface).
// Slot order is the colorblind-safety mechanism — assign in order, never cycle past 8.

export const SERIES_COLORS = [
  "#2a78d6", // blue
  "#eb6834", // orange
  "#1baf7a", // aqua
  "#eda100", // yellow
  "#e87ba4", // magenta
  "#008300", // green
  "#4a3aa7", // violet
  "#e34948", // red
] as const;

/** Max distinct series before the rest fold into "Other". */
export const MAX_SERIES = SERIES_COLORS.length;

/** Neutral used for the folded "Other" bucket so it never steals a categorical slot. */
export const OTHER_COLOR = "#b5b3ab";

export const CHART = {
  surface: "#ffffff",
  textPrimary: "#0b0b0b",
  textSecondary: "#52514e",
  muted: "#898781",
  grid: "#e9e8e2",
  axis: "#c3c2b7",
  good: "#006300",
  goodBg: "#e7f5e7",
  bad: "#b42323",
  badBg: "#fbeaea",
  neutralBg: "#f1f0ec",
} as const;

/** Stable color for series `index`; "Other" gets the neutral. */
export function seriesColor(index: number, name?: string, override?: string | null): string {
  if (name === "Other") return OTHER_COLOR;
  if (override && index === 0) return override;
  return SERIES_COLORS[index % SERIES_COLORS.length];
}
