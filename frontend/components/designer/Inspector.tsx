"use client";

import { useState, type ReactNode } from "react";
import { ChevronRight, Code, Filter as FilterIcon, Plus, Settings2, Sparkles, Star, X } from "lucide-react";
import { ArchetypeParamsForm } from "@/components/archetypes/ArchetypeParamsForm";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Input, Switch, Textarea } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { needsData, useDesigner } from "@/lib/stores/designer";
import type { ColumnInfo, Filter, FilterOp, WidgetOptions, WidgetSpec, WidgetType } from "@/lib/types";
import { cn, shortTable } from "@/lib/utils";
import { useArchetypes, useColumns, useEffectiveTable, useTables } from "./data";
import { compatibleTypes, typeLabel, WidgetIcon } from "./helpers";

export function Inspector() {
  const widget = useDesigner((s) => s.widgets.find((w) => w.id === s.selectedId) ?? null);
  return (
    <aside className="flex w-80 shrink-0 flex-col overflow-y-auto border-l border-zinc-200 bg-white">
      {widget ? <WidgetInspector key={widget.id} widget={widget} /> : <FormatInspector />}
    </aside>
  );
}

function Section({
  title,
  icon,
  children,
  defaultOpen = true,
  right,
}: {
  title: string;
  icon?: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  right?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="border-b border-zinc-100">
      <div className="flex items-center justify-between px-4 py-2.5">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-zinc-500 uppercase hover:text-zinc-800"
        >
          <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
          {icon}
          {title}
        </button>
        {right}
      </div>
      {open && <div className="flex flex-col gap-3 px-4 pb-4">{children}</div>}
    </section>
  );
}

/** Shown when no widget is selected: format-level settings. */
function FormatInspector() {
  const defaultSource = useDesigner((s) => s.default_source);
  const setMeta = useDesigner((s) => s.setMeta);
  const widgets = useDesigner((s) => s.widgets);
  const select = useDesigner((s) => s.select);
  const tables = useTables();
  return (
    <>
      <div className="border-b border-zinc-100 px-4 py-4">
        <div className="text-sm font-semibold text-zinc-900">Report settings</div>
        <p className="mt-0.5 text-xs text-zinc-500">Select a widget on the canvas to edit it.</p>
      </div>
      <Section title="Default data source">
        <Field hint="Widgets without their own source query this table.">
          <Select
            value={defaultSource?.table ?? ""}
            placeholder={tables.loading ? "Loading tables…" : "Choose a table…"}
            onValueChange={(t) => setMeta({ default_source: t ? { table: t } : null })}
            options={tableOptions(tables.data, defaultSource?.table)}
          />
        </Field>
        {tables.error && <p className="text-xs text-red-600">{tables.error}</p>}
      </Section>
      <Section title={`Widgets (${widgets.length})`}>
        {widgets.length === 0 ? (
          <p className="text-xs text-zinc-500">No widgets yet.</p>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {[...widgets]
              .sort((a, b) => a.layout.y - b.layout.y || a.layout.x - b.layout.x)
              .map((w) => (
                <li key={w.id}>
                  <button
                    type="button"
                    onClick={() => select(w.id)}
                    className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-zinc-700 hover:bg-zinc-50"
                  >
                    <WidgetIcon type={w.type} className="size-3.5 text-zinc-400" />
                    <span className="truncate">{w.title || w.options.text || typeLabel(w.type)}</span>
                  </button>
                </li>
              ))}
          </ul>
        )}
      </Section>
    </>
  );
}

function tableOptions(tables: { table: string; kind: string }[] | undefined, current?: string | null) {
  const opts = (tables ?? []).map((t) => ({ value: t.table, label: `${t.table}${t.kind === "VIEW" ? " (view)" : ""}` }));
  if (current && !opts.some((o) => o.value === current)) opts.unshift({ value: current, label: current });
  return opts;
}

function WidgetInspector({ widget }: { widget: WidgetSpec }) {
  const update = useDesigner((s) => s.updateWidget);
  const select = useDesigner((s) => s.select);
  const params = useDesigner((s) => s.params);
  const defaultTable = useDesigner((s) => s.default_source?.table ?? null);
  const preview = useDesigner((s) => s.previews[widget.id]);
  const tables = useTables();
  const table = useEffectiveTable(widget);
  const columns = useColumns(table);
  const dataWidget = needsData(widget.type);

  const setOptions = (patch: Partial<WidgetOptions>) =>
    update(widget.id, (w) => ({ ...w, options: { ...w.options, ...patch } }));

  return (
    <>
      <div className="flex items-start justify-between gap-2 border-b border-zinc-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
            <WidgetIcon type={widget.type} className="size-4" />
          </span>
          <div>
            <div className="text-sm font-semibold text-zinc-900">{typeLabel(widget.type)}</div>
            <div className="font-mono text-[10px] text-zinc-400">{widget.id}</div>
          </div>
        </div>
        <Button size="icon-sm" variant="ghost" title="Close" onClick={() => select(null)}>
          <X className="size-4" />
        </Button>
      </div>

      <Section title="General">
        {widget.type !== "heading" && (
          <Field label="Title">
            <Input value={widget.title} onChange={(e) => update(widget.id, { title: e.target.value })} />
          </Field>
        )}
        <Field label="Widget type">
          <Select
            value={widget.type}
            onValueChange={(t) => update(widget.id, { type: t as WidgetType })}
            options={compatibleTypes(widget.type).map((t) => ({ value: t, label: typeLabel(t) }))}
          />
        </Field>
      </Section>

      {dataWidget && (
        <>
          <Section title="Data">
            <Field label="Data source">
              <Select
                value={widget.source?.table ?? ""}
                onValueChange={(t) => update(widget.id, { source: t ? { table: t } : null })}
                options={tableOptions(tables.data, widget.source?.table)}
              >
                <option value="">Format default{defaultTable ? ` (${shortTable(defaultTable)})` : ""}</option>
              </Select>
            </Field>
            <ArchetypeEditor widget={widget} columns={columns.data ?? []} columnsLoading={columns.loading} />
          </Section>

          <Section
            title={`Filters${widget.filters.length ? ` (${widget.filters.length})` : ""}`}
            icon={<FilterIcon className="size-3" />}
            defaultOpen={widget.filters.length > 0}
          >
            <FiltersEditor widget={widget} columns={columns.data ?? []} />
          </Section>

          {params.length > 0 && (
            <Section title="Runtime parameters">
              <p className="text-xs text-zinc-500">Uncheck to ignore a parameter for this widget (e.g. a company-wide benchmark).</p>
              {params.map((p) => (
                <Checkbox
                  key={p.name}
                  label={
                    <span>
                      Apply <b className="font-medium">{p.label}</b>
                      {p.column && <span className="ml-1 font-mono text-[10px] text-zinc-400">{p.column}</span>}
                    </span>
                  }
                  checked={!widget.ignore_params.includes(p.name)}
                  onChange={(on) =>
                    update(widget.id, (w) => ({
                      ...w,
                      ignore_params: on ? w.ignore_params.filter((n) => n !== p.name) : [...w.ignore_params, p.name],
                    }))
                  }
                />
              ))}
            </Section>
          )}
        </>
      )}

      <Section title="Display" icon={<Settings2 className="size-3" />}>
        {widget.type === "heading" && (
          <Field label="Heading text">
            <Input value={widget.options.text ?? ""} onChange={(e) => setOptions({ text: e.target.value })} />
          </Field>
        )}
        {widget.type === "text" && (
          <>
            <Switch
              label={
                <span className="flex items-center gap-1.5">
                  <Sparkles className="size-3.5 text-indigo-500" /> Narrative (AI-generated at run time)
                </span>
              }
              checked={widget.options.narrative}
              onChange={(v) => setOptions({ narrative: v })}
            />
            <Field
              label={widget.options.narrative ? "Instructions for the AI (optional)" : "Text"}
              hint={
                widget.options.narrative
                  ? "The agent summarizes this report's numbers into this box when a PDF is generated."
                  : "Markdown is supported."
              }
            >
              <Textarea
                value={widget.options.text ?? ""}
                onChange={(e) => setOptions({ text: e.target.value })}
                className="min-h-28"
              />
            </Field>
          </>
        )}
        {dataWidget && (
          <>
            <Field label="Number format">
              <Select
                value={widget.options.format}
                onValueChange={(v) => setOptions({ format: v as WidgetOptions["format"] })}
                options={[
                  { value: "number", label: "Number (1,234.5)" },
                  { value: "currency", label: "Currency ($1,234)" },
                  { value: "compact", label: "Compact (1.2K)" },
                  { value: "percent", label: "Percent (12.3%)" },
                ]}
              />
            </Field>
            {widget.type !== "kpi" && widget.type !== "table" && (
              <>
                <Switch label="Show legend" checked={widget.options.show_legend} onChange={(v) => setOptions({ show_legend: v })} />
                <Switch label="Show data labels" checked={widget.options.show_labels} onChange={(v) => setOptions({ show_labels: v })} />
              </>
            )}
            <Field label="Accent color">
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={widget.options.color || "#6366f1"}
                  onChange={(e) => setOptions({ color: e.target.value })}
                  className="h-8 w-10 cursor-pointer rounded border border-zinc-200 bg-white p-0.5"
                />
                {widget.options.color ? (
                  <button type="button" className="text-xs text-zinc-500 hover:text-zinc-800" onClick={() => setOptions({ color: null })}>
                    Reset to theme
                  </button>
                ) : (
                  <span className="text-xs text-zinc-400">Theme default</span>
                )}
              </div>
            </Field>
          </>
        )}
      </Section>

      {dataWidget && (
        <Section title="SQL" icon={<Code className="size-3" />} defaultOpen={false}>
          {preview?.data?.sql ? (
            <pre className="max-h-72 overflow-auto rounded-lg bg-zinc-900 p-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-zinc-100">
              {preview.data.sql}
            </pre>
          ) : (
            <p className="text-xs text-zinc-500">{preview?.loading ? "Running…" : "No query yet."}</p>
          )}
          {preview?.data && (
            <p className="text-[11px] text-zinc-500">
              {preview.data.rows.length} row{preview.data.rows.length === 1 ? "" : "s"} ·{" "}
              {preview.data.columns.map((c) => c.name).join(", ")}
            </p>
          )}
          {preview?.error && <p className="text-xs whitespace-pre-wrap text-red-600">{preview.error}</p>}
        </Section>
      )}
    </>
  );
}

function ArchetypeEditor({
  widget,
  columns,
  columnsLoading,
}: {
  widget: WidgetSpec;
  columns: ColumnInfo[];
  columnsLoading: boolean;
}) {
  const update = useDesigner((s) => s.updateWidget);
  const archetypes = useArchetypes();
  const list = archetypes.data ?? [];
  const spec = list.find((a) => a.id === widget.archetype?.id);
  const suggested = list.filter((a) => a.suggested_widgets.includes(widget.type));
  const others = list.filter((a) => !a.suggested_widgets.includes(widget.type));

  return (
    <>
      <Field
        label={
          <span className="flex items-center justify-between">
            Archetype
            {spec?.kind === "custom" && <Badge tone="indigo">custom</Badge>}
          </span>
        }
        hint={spec?.description}
      >
        <Select
          value={widget.archetype?.id ?? ""}
          placeholder={archetypes.loading ? "Loading archetypes…" : "Choose an archetype…"}
          onValueChange={(id) => {
            const a = list.find((x) => x.id === id);
            update(widget.id, { archetype: a ? { id: a.id, params: structuredClone(a.example_params ?? {}) } : null });
          }}
        >
          {suggested.length > 0 && (
            <optgroup label={`★ Suggested for ${typeLabel(widget.type)}`}>
              {suggested.map((a) => (
                <option key={a.id} value={a.id}>
                  ★ {a.name}
                  {a.kind === "custom" ? " (custom)" : ""}
                </option>
              ))}
            </optgroup>
          )}
          {others.length > 0 && (
            <optgroup label="Other archetypes">
              {others.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                  {a.kind === "custom" ? " (custom)" : ""}
                </option>
              ))}
            </optgroup>
          )}
          {widget.archetype && !spec && <option value={widget.archetype.id}>{widget.archetype.id}</option>}
        </Select>
      </Field>
      {spec && !spec.suggested_widgets.includes(widget.type) && spec.suggested_widgets.length > 0 && (
        <p className="flex items-start gap-1 text-[11px] text-amber-700">
          <Star className="mt-0.5 size-3 shrink-0" />
          Usually shown as {spec.suggested_widgets.map(typeLabel).join(", ")}.
        </p>
      )}
      {archetypes.error && <p className="text-xs text-red-600">{archetypes.error}</p>}
      {spec && widget.archetype && (
        <div className="rounded-lg border border-zinc-200 bg-zinc-50/60 p-3">
          {columnsLoading && <p className="mb-2 text-[11px] text-zinc-400">Loading columns…</p>}
          <ArchetypeParamsForm
            spec={spec}
            columns={columns}
            value={widget.archetype.params}
            onChange={(params) =>
              update(widget.id, (w) => ({ ...w, archetype: w.archetype ? { ...w.archetype, params } : w.archetype }))
            }
          />
        </div>
      )}
    </>
  );
}

const OPS: { value: FilterOp; label: string }[] = [
  { value: "eq", label: "=" },
  { value: "neq", label: "≠" },
  { value: "in", label: "in" },
  { value: "gt", label: ">" },
  { value: "gte", label: "≥" },
  { value: "lt", label: "<" },
  { value: "lte", label: "≤" },
  { value: "between", label: "between" },
  { value: "contains", label: "contains" },
];

function coerce(raw: string, type: ColumnInfo["type"] | undefined): unknown {
  if (type === "number" && raw.trim() !== "" && !Number.isNaN(Number(raw))) return Number(raw);
  return raw;
}

function FiltersEditor({ widget, columns }: { widget: WidgetSpec; columns: ColumnInfo[] }) {
  const update = useDesigner((s) => s.updateWidget);
  const params = useDesigner((s) => s.params);

  const setFilters = (fn: (f: Filter[]) => Filter[]) => update(widget.id, (w) => ({ ...w, filters: fn(w.filters) }));
  const patch = (i: number, p: Partial<Filter>) => setFilters((fs) => fs.map((f, j) => (j === i ? { ...f, ...p } : f)));

  return (
    <>
      {widget.filters.length === 0 && <p className="text-xs text-zinc-500">No static filters. Runtime parameters still apply.</p>}
      {widget.filters.map((f, i) => {
        const colType = columns.find((c) => c.name === f.column)?.type;
        const valueStr = Array.isArray(f.value) ? f.value.join(", ") : f.value == null ? "" : String(f.value);
        const range = Array.isArray(f.value) ? f.value : [undefined, undefined];
        return (
          <div key={i} className="flex flex-col gap-1.5 rounded-lg border border-zinc-200 p-2">
            <div className="flex items-center gap-1.5">
              <Select
                selectSize="sm"
                value={f.column}
                placeholder="Column…"
                onValueChange={(c) => patch(i, { column: c })}
                options={[
                  ...columns.map((c) => ({ value: c.name, label: c.name })),
                  ...(f.column && !columns.some((c) => c.name === f.column) ? [{ value: f.column, label: f.column }] : []),
                ]}
              />
              <Select
                selectSize="sm"
                className="w-24 shrink-0"
                value={f.op}
                onValueChange={(op) => patch(i, { op: op as FilterOp, value: op === "between" || op === "in" ? [] : "" })}
                options={OPS}
              />
              <button
                type="button"
                title="Remove filter"
                onClick={() => setFilters((fs) => fs.filter((_, j) => j !== i))}
                className="shrink-0 rounded p-1 text-zinc-400 hover:bg-red-50 hover:text-red-600"
              >
                <X className="size-3.5" />
              </button>
            </div>
            {f.param ? (
              <div className="flex items-center justify-between rounded-md bg-indigo-50 px-2 py-1 text-xs text-indigo-700">
                Bound to parameter <b>{params.find((p) => p.name === f.param)?.label ?? f.param}</b>
                <button type="button" className="underline" onClick={() => patch(i, { param: null })}>
                  unbind
                </button>
              </div>
            ) : f.op === "between" ? (
              <div className="flex items-center gap-1.5">
                <Input
                  inputSize="sm"
                  type={colType === "date" ? "date" : "text"}
                  value={range[0] == null ? "" : String(range[0])}
                  onChange={(e) => patch(i, { value: [coerce(e.target.value, colType), range[1]] })}
                />
                <span className="text-xs text-zinc-400">and</span>
                <Input
                  inputSize="sm"
                  type={colType === "date" ? "date" : "text"}
                  value={range[1] == null ? "" : String(range[1])}
                  onChange={(e) => patch(i, { value: [range[0], coerce(e.target.value, colType)] })}
                />
              </div>
            ) : (
              <Input
                inputSize="sm"
                type={colType === "date" ? "date" : "text"}
                placeholder={f.op === "in" ? "Comma-separated values" : "Value"}
                value={valueStr}
                onChange={(e) =>
                  patch(i, {
                    value:
                      f.op === "in"
                        ? e.target.value
                            .split(",")
                            .map((s) => s.trim())
                            .filter(Boolean)
                            .map((s) => coerce(s, colType))
                        : coerce(e.target.value, colType),
                  })
                }
              />
            )}
            {!f.param && params.length > 0 && (
              <Select
                selectSize="sm"
                value=""
                onValueChange={(p) => p && patch(i, { param: p, value: null })}
                placeholder="…or bind to a runtime parameter"
                options={params.map((p) => ({ value: p.name, label: p.label }))}
              />
            )}
          </div>
        );
      })}
      <Button
        size="sm"
        variant="outline"
        onClick={() => setFilters((fs) => [...fs, { column: columns[0]?.name ?? "", op: "eq", value: "" }])}
      >
        <Plus className="size-3.5" /> Add filter
      </Button>
    </>
  );
}
