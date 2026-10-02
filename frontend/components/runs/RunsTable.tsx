"use client";

import { format } from "date-fns";
import { Download, Eye, FileText } from "lucide-react";
import { formatParamValue } from "@/components/params/presets";
import { Badge } from "@/components/ui/Badge";
import { runApi } from "@/lib/endpoints";
import type { RunSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

export function RunStatusBadge({ status }: { status: string }) {
  const s = status.toLowerCase();
  const tone = s === "completed" ? "green" : s === "failed" ? "red" : "amber";
  return <Badge tone={tone}>{status}</Badge>;
}

export function RunValues({ values }: { values: RunSummary["values"] }) {
  const entries = Object.entries(values ?? {});
  if (!entries.length) return <span className="text-zinc-400">No parameters</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {entries.map(([k, v]) => (
        <Badge key={k} className="font-normal">
          <span className="text-zinc-500">{k}:</span> {formatParamValue(v)}
        </Badge>
      ))}
    </span>
  );
}

export function RunsTable({
  runs,
  onView,
  activeId,
  compact,
}: {
  runs: RunSummary[];
  onView?: (run: RunSummary) => void;
  activeId?: string | null;
  compact?: boolean;
}) {
  if (!runs.length) {
    return (
      <div className="flex flex-col items-center gap-2 px-6 py-10 text-center text-sm text-zinc-500">
        <FileText className="size-6 text-zinc-300" />
        No reports generated yet.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-100 text-left text-xs font-medium tracking-wide text-zinc-500 uppercase">
            <th className="px-5 py-2.5">Report</th>
            <th className="px-3 py-2.5">Parameters</th>
            {!compact && <th className="px-3 py-2.5">By</th>}
            <th className="px-3 py-2.5">Generated</th>
            <th className="px-3 py-2.5">Status</th>
            <th className="px-5 py-2.5 text-right">PDF</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => {
            const ok = r.status === "completed" && !!r.pdf_url;
            return (
              <tr
                key={r.id}
                className={cn(
                  "border-b border-zinc-50 last:border-0 hover:bg-zinc-50/60",
                  activeId === r.id && "bg-indigo-50/50",
                )}
              >
                <td className="px-5 py-2.5 font-medium text-zinc-900">{r.format_name}</td>
                <td className="px-3 py-2.5">
                  <RunValues values={r.values} />
                </td>
                {!compact && <td className="px-3 py-2.5 text-zinc-600">{r.created_by_name ?? "—"}</td>}
                <td className="px-3 py-2.5 whitespace-nowrap text-zinc-600">
                  {format(new Date(r.created_at), "MMM d, yyyy HH:mm")}
                </td>
                <td className="px-3 py-2.5" title={r.error ?? undefined}>
                  <RunStatusBadge status={r.status} />
                </td>
                <td className="px-5 py-2.5">
                  <div className="flex justify-end gap-1">
                    {ok && onView && (
                      <button
                        type="button"
                        onClick={() => onView(r)}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100"
                      >
                        <Eye className="size-3.5" /> View
                      </button>
                    )}
                    {ok && (
                      <a
                        href={runApi.pdfUrl(r.id, true)}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-50"
                      >
                        <Download className="size-3.5" /> Download
                      </a>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
