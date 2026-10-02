"use client";

import { useState } from "react";
import { CalendarRange, Eye, SlidersHorizontal, UserRound } from "lucide-react";
import { ParamValueInput } from "@/components/params/ParamValueInput";
import { PARAM_PRESETS } from "@/components/params/presets";
import { Button } from "@/components/ui/Button";
import { useDesigner } from "@/lib/stores/designer";
import { ParamsDialog } from "./ParamsDialog";

/** Runtime parameter definitions + the preview values used by the live canvas. */
export function ParamBar() {
  const params = useDesigner((s) => s.params);
  const setParams = useDesigner((s) => s.setParams);
  const values = useDesigner((s) => s.previewValues);
  const setValue = useDesigner((s) => s.setPreviewValue);
  const table = useDesigner((s) => s.default_source?.table ?? null);
  const [open, setOpen] = useState(false);

  const has = (n: string) => params.some((p) => p.name === n);

  return (
    <div className="flex min-h-12 flex-wrap items-center gap-x-4 gap-y-2 border-b border-zinc-200 bg-zinc-50/80 px-4 py-2">
      <div className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-zinc-500 uppercase">
        <SlidersHorizontal className="size-3.5" /> Parameters
      </div>
      {params.length === 0 && (
        <span className="text-xs text-zinc-500">None — the report shows all data.</span>
      )}
      {params.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="text-xs font-medium text-zinc-700">{p.label}</span>
          <div className={p.type === "date_range" ? "" : "w-56"}>
            <ParamValueInput
              def={p}
              table={table}
              size="sm"
              showDates="custom"
              value={values[p.name]}
              onChange={(v) => setValue(p.name, v)}
              anyLabel={`Any ${p.label.toLowerCase()} (preview)`}
            />
          </div>
        </div>
      ))}
      <div className="ml-auto flex items-center gap-1.5">
        {params.length > 0 && (
          <span className="mr-1 hidden items-center gap-1 text-[11px] text-zinc-400 xl:flex">
            <Eye className="size-3" /> preview values, chosen again at generation
          </span>
        )}
        {!has("client") && (
          <Button size="sm" variant="ghost" onClick={() => setParams([...params, { ...PARAM_PRESETS.client }])}>
            <UserRound className="size-3.5" /> + Client
          </Button>
        )}
        {!has("period") && (
          <Button size="sm" variant="ghost" onClick={() => setParams([...params, { ...PARAM_PRESETS.period }])}>
            <CalendarRange className="size-3.5" /> + Period
          </Button>
        )}
        <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
          Edit parameters
        </Button>
      </div>
      <ParamsDialog open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
