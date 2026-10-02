"use client";

import { useState } from "react";
import { CalendarRange, Plus, Trash2, UserRound } from "lucide-react";
import { PARAM_PRESETS } from "@/components/params/presets";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Checkbox, Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { useDesigner } from "@/lib/stores/designer";
import type { ParamDef, ParamType } from "@/lib/types";
import { useColumns } from "./data";

const TYPES: { value: ParamType; label: string }[] = [
  { value: "client", label: "Client" },
  { value: "date_range", label: "Date range" },
  { value: "select", label: "Select (dropdown)" },
  { value: "string", label: "Text" },
  { value: "number", label: "Number" },
];

const slug = (s: string) =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");

export function ParamsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  // Remount the editor each time the dialog opens so it starts from the store's params.
  return (
    <Dialog
      open={open}
      onClose={onClose}
      className="max-w-3xl"
      title="Runtime parameters"
      description="Values the report viewer chooses when generating a PDF. A parameter bound to a column filters every widget on that column."
    >
      {open && <ParamsEditor onClose={onClose} />}
    </Dialog>
  );
}

function ParamsEditor({ onClose }: { onClose: () => void }) {
  const params = useDesigner((s) => s.params);
  const setParams = useDesigner((s) => s.setParams);
  const table = useDesigner((s) => s.default_source?.table ?? null);
  const columns = useColumns(table);
  const [draft, setDraft] = useState<ParamDef[]>(() => structuredClone(params));

  const patch = (i: number, p: Partial<ParamDef>) => setDraft((d) => d.map((x, j) => (j === i ? { ...x, ...p } : x)));
  const addPreset = (k: "client" | "period") => {
    if (draft.some((p) => p.name === PARAM_PRESETS[k].name)) return;
    setDraft((d) => [...d, { ...PARAM_PRESETS[k] }]);
  };
  const names = draft.map((p) => p.name);
  const dupes = names.filter((n, i) => names.indexOf(n) !== i);
  const invalid = draft.some((p) => !p.name || !p.label) || dupes.length > 0;

  const columnOptions = (columns.data ?? []).map((c) => ({ value: c.name, label: `${c.name} (${c.type})` }));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-zinc-500">Quick add:</span>
        <Button size="sm" variant="outline" onClick={() => addPreset("client")} disabled={names.includes("client")}>
          <UserRound className="size-3.5" /> Client
        </Button>
        <Button size="sm" variant="outline" onClick={() => addPreset("period")} disabled={names.includes("period")}>
          <CalendarRange className="size-3.5" /> Period
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() =>
            setDraft((d) => [...d, { name: `param_${d.length + 1}`, label: "New parameter", type: "select", column: null, required: false }])
          }
        >
          <Plus className="size-3.5" /> Custom
        </Button>
      </div>

      {draft.length === 0 ? (
        <p className="rounded-lg border border-dashed border-zinc-200 px-4 py-6 text-center text-sm text-zinc-500">
          No parameters. Most client reports use <b>Client</b> and <b>Period</b>.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-500">
                <th className="pb-2 font-medium">Label</th>
                <th className="pb-2 pl-2 font-medium">Name</th>
                <th className="pb-2 pl-2 font-medium">Type</th>
                <th className="pb-2 pl-2 font-medium">Filters column</th>
                <th className="pb-2 pl-2 font-medium">Required</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {draft.map((p, i) => (
                <tr key={i} className="align-top">
                  <td className="py-1">
                    <Input
                      inputSize="sm"
                      value={p.label}
                      onChange={(e) => {
                        const label = e.target.value;
                        const autoName = p.name === slug(p.label) || p.name.startsWith("param_");
                        patch(i, { label, ...(autoName ? { name: slug(label) } : {}) });
                      }}
                    />
                  </td>
                  <td className="py-1 pl-2">
                    <Input
                      inputSize="sm"
                      className={dupes.includes(p.name) ? "border-red-400 font-mono" : "font-mono"}
                      value={p.name}
                      onChange={(e) => patch(i, { name: slug(e.target.value) })}
                    />
                  </td>
                  <td className="py-1 pl-2">
                    <Select
                      selectSize="sm"
                      className="w-36"
                      value={p.type}
                      onValueChange={(t) => patch(i, { type: t as ParamType })}
                      options={TYPES}
                    />
                  </td>
                  <td className="py-1 pl-2">
                    <Select
                      selectSize="sm"
                      className="w-48"
                      value={p.column ?? ""}
                      placeholder="(none — only for SQL templates)"
                      onValueChange={(c) => patch(i, { column: c || null })}
                      options={
                        p.column && !columnOptions.some((o) => o.value === p.column)
                          ? [{ value: p.column, label: p.column }, ...columnOptions]
                          : columnOptions
                      }
                    />
                  </td>
                  <td className="py-1 pl-4">
                    <Checkbox label="" checked={p.required ?? true} onChange={(v) => patch(i, { required: v })} className="mt-1.5" />
                  </td>
                  <td className="py-1 pl-1">
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      className="text-zinc-400 hover:bg-red-50 hover:text-red-600"
                      onClick={() => setDraft((d) => d.filter((_, j) => j !== i))}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {dupes.length > 0 && <p className="mt-2 text-xs text-red-600">Parameter names must be unique.</p>}
        </div>
      )}

      <div className="flex justify-end gap-2 border-t border-zinc-100 pt-4">
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button
          disabled={invalid}
          onClick={() => {
            setParams(draft);
            onClose();
          }}
        >
          Apply parameters
        </Button>
      </div>
    </div>
  );
}
