"use client";

import { useState } from "react";
import { toast } from "sonner";
import { ArchetypeParamsForm } from "@/components/archetypes/ArchetypeParamsForm";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Checkbox, Field, Input, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Tabs } from "@/components/ui/Tabs";
import { archetypeApi } from "@/lib/endpoints";
import { useDesigner } from "@/lib/stores/designer";
import type { ArchetypeSpec, WidgetType } from "@/lib/types";
import { errorMessage } from "@/lib/utils";
import { useColumns } from "./data";
import { TYPE_LABELS } from "./helpers";

const SQL_EXAMPLE = `SELECT PRODUCT_LINE, SUM(SALES) AS REVENUE
FROM {{table}}
WHERE {{where}}
GROUP BY PRODUCT_LINE
ORDER BY REVENUE DESC`;

const DATA_TYPES: WidgetType[] = ["table", "bar", "stacked_bar", "line", "area", "pie", "donut", "kpi", "scatter"];

export function CustomArchetypeDialog({
  open,
  onClose,
  archetypes,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  archetypes: ArchetypeSpec[];
  onCreated: (spec: ArchetypeSpec) => void;
}) {
  const builtins = archetypes.filter((a) => a.kind === "builtin");
  const table = useDesigner((s) => s.default_source?.table ?? null);
  const columns = useColumns(open ? table : null);
  const [mode, setMode] = useState<"preset" | "sql">("preset");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [baseId, setBaseId] = useState("");
  const [baseParams, setBaseParams] = useState<Record<string, unknown>>({});
  const [sql, setSql] = useState(SQL_EXAMPLE);
  const [widgets, setWidgets] = useState<WidgetType[]>(["table"]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const base = builtins.find((a) => a.id === baseId);

  const reset = () => {
    setName("");
    setDescription("");
    setBaseId("");
    setBaseParams({});
    setSql(SQL_EXAMPLE);
    setWidgets(["table"]);
    setError(null);
  };

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      const spec = await archetypeApi.createCustom({
        name: name.trim(),
        description: description.trim(),
        ...(mode === "preset" ? { base: { id: baseId, params: baseParams } } : { sql }),
        suggested_widgets: widgets,
      });
      toast.success(`Custom archetype “${spec.name}” created`);
      onCreated(spec);
      reset();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const valid = name.trim() && (mode === "preset" ? !!baseId : sql.trim().length > 0) && widgets.length > 0;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      className="max-w-2xl"
      title="New custom archetype"
      description="A named computation your company can reuse in any report format."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} loading={saving} disabled={!valid}>
            Create archetype
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Quarterly revenue by product line" />
          </Field>
          <Field label="Description">
            <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What it computes" />
          </Field>
        </div>
        <Tabs
          value={mode}
          onChange={setMode}
          items={[
            { value: "preset", label: "Preset of a built-in" },
            { value: "sql", label: "SQL template" },
          ]}
        />
        {mode === "preset" ? (
          <div className="flex flex-col gap-3">
            <Field label="Base archetype" hint={base?.description}>
              <Select
                value={baseId}
                placeholder="Choose a built-in archetype…"
                onValueChange={(id) => {
                  setBaseId(id);
                  const a = builtins.find((x) => x.id === id);
                  setBaseParams(structuredClone(a?.example_params ?? {}));
                  if (a?.suggested_widgets.length) setWidgets(a.suggested_widgets.slice(0, 2));
                }}
                options={builtins.map((a) => ({ value: a.id, label: a.name }))}
              />
            </Field>
            {base && (
              <div className="rounded-lg border border-zinc-200 bg-zinc-50/60 p-3">
                <div className="mb-2 text-xs font-medium text-zinc-700">Preset parameters</div>
                <ArchetypeParamsForm
                  spec={base}
                  columns={columns.data ?? []}
                  value={baseParams}
                  onChange={setBaseParams}
                />
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <Field label="SELECT template">
              <Textarea
                value={sql}
                onChange={(e) => setSql(e.target.value)}
                className="min-h-40 font-mono text-xs"
                spellCheck={false}
              />
            </Field>
            <div className="rounded-lg border border-indigo-100 bg-indigo-50/50 px-3 py-2.5 text-xs text-zinc-600">
              <div className="mb-1 font-medium text-zinc-800">Template placeholders</div>
              <ul className="list-disc space-y-0.5 pl-4">
                <li>
                  <code className="rounded bg-white px-1 font-mono">{"{{table}}"}</code> is replaced by the widget&apos;s
                  data source.
                </li>
                <li>
                  <code className="rounded bg-white px-1 font-mono">{"{{where}}"}</code> expands to the widget filters
                  plus runtime parameters (client, period…). Use it in your WHERE clause.
                </li>
                <li>
                  <code className="rounded bg-white px-1 font-mono">%(client)s</code> binds a runtime parameter by name
                  as a safe bind variable (never string-concatenated).
                </li>
                <li>Only a single read-only SELECT is allowed.</li>
              </ul>
            </div>
          </div>
        )}
        <Field label="Works best as">
          <div className="flex flex-wrap gap-x-4 gap-y-2">
            {DATA_TYPES.map((t) => (
              <Checkbox
                key={t}
                label={TYPE_LABELS[t]}
                checked={widgets.includes(t)}
                onChange={(on) => setWidgets((ws) => (on ? [...ws, t] : ws.filter((x) => x !== t)))}
              />
            ))}
          </div>
        </Field>
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm whitespace-pre-wrap text-red-700">{error}</p>}
      </div>
    </Dialog>
  );
}
