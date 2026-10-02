"use client";

import type { WidgetBodyProps } from "./chartData";
import { LineLikeChart } from "./LineWidget";

/** Area chart; `options.extra.stacked` stacks multiple series. */
export function AreaWidget(props: WidgetBodyProps) {
  return <LineLikeChart {...props} variant="area" />;
}
