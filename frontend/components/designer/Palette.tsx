"use client";

import { useState } from "react";
import { Layers, Plus, Puzzle, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { WIDGET_CATALOG } from "@/components/widgets/catalog";
import { Spinner } from "@/components/ui/Spinner";
import { archetypeApi } from "@/lib/endpoints";
import { useSession } from "@/lib/stores/session";
import { newWidget, useDesigner } from "@/lib/stores/designer";
import type { ArchetypeConfig, ArchetypeSpec, WidgetType } from "@/lib/types";
import { errorMessage } from "@/lib/utils";
import { CustomArchetypeDialog } from "./CustomArchetypeDialog";
import { useArchetypes } from "./data";
import { defaultArchetypeFor, iconFor, setPaletteDrag, typeLabel, WidgetIcon } from "./helpers";

export function Palette() {
  const archetypes = useArchetypes();
  const addWidget = useDesigner((s) => s.addWidget);
  const [dialogOpen, setDialogOpen] = useState(false);
  const isDesigner = useSession((s) => s.me?.role === "designer");

  const add = (type: WidgetType, archetype?: ArchetypeConfig | null, title?: string) => {
    addWidget(newWidget(type, { archetype: archetype ?? defaultArchetypeFor(type, archetypes.data), title }), {
      atBottom: true,
    });
  };

  const startDrag = (e: React.DragEvent, type: WidgetType, archetype?: ArchetypeConfig | null, title?: string) => {
    setPaletteDrag({ type, archetype: archetype ?? defaultArchetypeFor(type, archetypes.data), title });
    e.dataTransfer.setData("text/plain", type);
    e.dataTransfer.effectAllowed = "copy";
  };

  const custom = (archetypes.data ?? []).filter((a) => a.kind === "custom");

  const removeCustom = async (a: ArchetypeSpec) => {
    if (!window.confirm(`Delete custom archetype “${a.name}”? Widgets using it will stop working.`)) return;
    try {
      await archetypeApi.deleteCustom(a.id);
      archetypes.mutate((archetypes.data ?? []).filter((x) => x.id !== a.id));
      toast.success("Archetype deleted");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <aside className="flex w-60 shrink-0 flex-col overflow-y-auto border-r border-zinc-200 bg-white">
      <div className="px-4 pt-4 pb-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-zinc-500 uppercase">
          <Layers className="size-3.5" /> Widgets
        </div>
        <p className="mt-1 text-[11px] text-zinc-400">Drag onto the canvas or click to add.</p>
      </div>
      <div className="grid grid-cols-2 gap-2 px-3 pb-4">
        {WIDGET_CATALOG.map((c) => {
          const Icon = iconFor(c.type, c.icon);
          return (
            <button
              key={c.type}
              type="button"
              draggable
              onDragStart={(e) => startDrag(e, c.type)}
              onDragEnd={() => setPaletteDrag(null)}
              onClick={() => add(c.type)}
              className="flex cursor-grab flex-col items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-2 py-3 text-xs font-medium text-zinc-700 transition-colors hover:border-indigo-300 hover:bg-indigo-50/50 hover:text-indigo-700 active:cursor-grabbing"
            >
              <Icon className="size-5 text-zinc-500" />
              {c.label}
            </button>
          );
        })}
      </div>

      <div className="border-t border-zinc-100 px-4 pt-4 pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-zinc-500 uppercase">
            <Puzzle className="size-3.5" /> Custom archetypes
          </div>
          {isDesigner && (
            <button
              type="button"
              onClick={() => setDialogOpen(true)}
              className="flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-xs font-medium text-indigo-600 hover:bg-indigo-50"
            >
              <Plus className="size-3.5" /> New
            </button>
          )}
        </div>
        <p className="mt-1 text-[11px] text-zinc-400">Your company&apos;s reusable computations.</p>
      </div>
      <div className="flex flex-col gap-1.5 px-3 pb-4">
        {archetypes.loading && (
          <div className="flex items-center gap-2 px-1 text-xs text-zinc-500">
            <Spinner className="size-3" /> Loading…
          </div>
        )}
        {archetypes.error && <p className="px-1 text-xs text-red-600">{archetypes.error}</p>}
        {!archetypes.loading && !archetypes.error && custom.length === 0 && (
          <p className="rounded-lg border border-dashed border-zinc-200 px-3 py-3 text-center text-xs text-zinc-500">
            None yet. Save a preset or a SQL template to reuse it across formats.
          </p>
        )}
        {custom.map((a) => {
          const type = a.suggested_widgets[0] ?? "table";
          const cfg: ArchetypeConfig = { id: a.id, params: structuredClone(a.example_params ?? {}) };
          return (
            <div
              key={a.id}
              draggable
              onDragStart={(e) => startDrag(e, type, cfg, a.name)}
              onDragEnd={() => setPaletteDrag(null)}
              onClick={() => add(type, cfg, a.name)}
              title={a.description}
              className="group flex cursor-grab items-center gap-2 rounded-lg border border-zinc-200 px-2.5 py-2 text-left hover:border-indigo-300 hover:bg-indigo-50/50"
            >
              <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-indigo-50 text-indigo-600">
                <WidgetIcon type={type} className="size-3.5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-medium text-zinc-800">{a.name}</span>
                <span className="block truncate text-[11px] text-zinc-500">{typeLabel(type)}</span>
              </span>
              {isDesigner && (
                <button
                  type="button"
                  title="Delete archetype"
                  onClick={(e) => {
                    e.stopPropagation();
                    void removeCustom(a);
                  }}
                  className="rounded p-1 text-zinc-400 opacity-0 group-hover:opacity-100 hover:bg-red-50 hover:text-red-600"
                >
                  <Trash2 className="size-3.5" />
                </button>
              )}
            </div>
          );
        })}
      </div>
      <CustomArchetypeDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        archetypes={archetypes.data ?? []}
        onCreated={(spec) => {
          archetypes.mutate([...(archetypes.data ?? []), spec]);
          setDialogOpen(false);
        }}
      />
    </aside>
  );
}
