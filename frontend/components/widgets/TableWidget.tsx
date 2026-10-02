"use client";

import { clsx } from "clsx";
import { EmptyState } from "./ChartParts";
import { widgetFormat, type WidgetBodyProps } from "./chartData";
import { datePatternFor, formatCategory, formatForColumn, formatValue, humanize } from "./format";

/** Data table: sticky header, formatted numbers; scrolls in the app, shows every row in print. */
export function TableWidget({ spec, data, mode }: WidgetBodyProps) {
  const fmt = widgetFormat(spec);
  const print = mode === "print";
  if (!data.rows.length || !data.columns.length) return <EmptyState />;
  const patterns = Object.fromEntries(
    data.columns.filter((c) => c.type === "date").map((c) => [c.name, datePatternFor(data.rows.map((r) => r[c.name]))]),
  );
  const maxRows = typeof spec.options?.extra?.max_rows === "number" ? (spec.options.extra.max_rows as number) : undefined;
  const rows = maxRows ? data.rows.slice(0, maxRows) : data.rows;

  return (
    <div className={clsx("h-full w-full", print ? "overflow-visible" : "overflow-auto")}>
      <table className="w-full border-separate border-spacing-0 text-xs">
        <thead>
          <tr>
            {data.columns.map((c) => (
              <th
                key={c.name}
                scope="col"
                className={clsx(
                  "border-b border-zinc-200 bg-zinc-50 px-3 py-1.5 font-medium whitespace-nowrap text-zinc-600",
                  !print && "sticky top-0 z-10",
                  c.type === "number" ? "text-right" : "text-left",
                )}
              >
                {humanize(c.name)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={clsx(!print && "hover:bg-zinc-50", "break-inside-avoid")}>
              {data.columns.map((c) => {
                const v = r[c.name];
                const text =
                  c.type === "number"
                    ? formatValue(v, formatForColumn(c.name, fmt))
                    : c.type === "date"
                      ? formatCategory(v, patterns[c.name])
                      : v === null || v === undefined
                        ? "—"
                        : String(v);
                return (
                  <td
                    key={c.name}
                    className={clsx(
                      "border-b border-zinc-100 px-3 py-1.5 text-zinc-800",
                      c.type === "number" ? "text-right tabular-nums whitespace-nowrap" : "text-left",
                      c.name === "Other" || v === "Other" ? "text-zinc-500" : undefined,
                    )}
                  >
                    {text}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
