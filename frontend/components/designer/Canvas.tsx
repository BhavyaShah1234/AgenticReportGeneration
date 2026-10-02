"use client";

import { memo, useCallback, useMemo } from "react";
import ReactGridLayout, { useContainerWidth, type Layout, type LayoutItem } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import { AlertTriangle, Copy, GripVertical, MousePointerClick, Sparkles, Trash2 } from "lucide-react";
import { WidgetRenderer } from "@/components/widgets/WidgetRenderer";
import { Spinner } from "@/components/ui/Spinner";
import { newWidget, useDesigner } from "@/lib/stores/designer";
import type { WidgetSpec } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useWidgetPreview } from "./data";
import { getPaletteDrag, setPaletteDrag, typeLabel, WidgetIcon } from "./helpers";

const GRID = { cols: 12, rowHeight: 40, margin: [12, 12] as [number, number], containerPadding: [16, 16] as [number, number] };
const DROP_ID = "__dropping-elem__";

export function Canvas() {
  const widgets = useDesigner((s) => s.widgets);
  const applyLayout = useDesigner((s) => s.applyLayout);
  const addWidget = useDesigner((s) => s.addWidget);
  const select = useDesigner((s) => s.select);
  const markDirty = useDesigner((s) => s.markDirty);
  const { width, containerRef, mounted } = useContainerWidth();

  const layout = useMemo<Layout>(
    () => widgets.map((w) => ({ i: w.id, ...w.layout, minW: 2, minH: w.type === "heading" ? 1 : 2 })),
    [widgets],
  );

  const onLayoutChange = useCallback((l: Layout) => applyLayout(l.filter((x) => x.i !== DROP_ID)), [applyLayout]);

  const dropConfig = useMemo(
    () => ({
      enabled: true,
      defaultItem: { w: 6, h: 8 },
      onDragOver: () => {
        const d = getPaletteDrag();
        if (!d) return false as const;
        const size = newWidget(d.type).layout;
        return { w: size.w, h: size.h };
      },
    }),
    [],
  );

  const onDrop = useCallback(
    (_layout: Layout, item: LayoutItem | undefined) => {
      const d = getPaletteDrag();
      setPaletteDrag(null);
      if (!d || !item) return;
      addWidget(newWidget(d.type, { x: item.x, y: item.y, archetype: d.archetype, title: d.title }));
    },
    [addWidget],
  );

  return (
    <div
      className="designer-canvas relative min-h-full"
      ref={containerRef}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget || (e.target as HTMLElement).classList.contains("react-grid-layout"))
          select(null);
      }}
    >
      {widgets.length === 0 && <EmptyCanvas />}
      {mounted && (
        <ReactGridLayout
          width={width}
          layout={layout}
          gridConfig={GRID}
          dragConfig={{ enabled: true, cancel: ".no-drag", threshold: 4 }}
          resizeConfig={{ enabled: true, handles: ["se"] }}
          dropConfig={dropConfig}
          onLayoutChange={onLayoutChange}
          onDragStop={markDirty}
          onResizeStop={markDirty}
          onDrop={onDrop}
          className="min-h-[calc(100vh-11rem)]"
        >
          {widgets.map((w) => (
            <div key={w.id}>
              <CanvasItem widget={w} />
            </div>
          ))}
        </ReactGridLayout>
      )}
    </div>
  );
}

function EmptyCanvas() {
  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-8">
      <div className="flex max-w-sm flex-col items-center gap-3 rounded-2xl border border-dashed border-zinc-300 bg-white/80 px-8 py-10 text-center">
        <MousePointerClick className="size-7 text-indigo-500" />
        <div className="font-medium text-zinc-900">Start building your report</div>
        <p className="text-sm text-zinc-500">
          Drag widgets from the left palette, click one to add it, or{" "}
          <span className="inline-flex items-center gap-1 font-medium text-indigo-600">
            <Sparkles className="size-3.5" /> ask the agent
          </span>{" "}
          to draft the whole report.
        </p>
      </div>
    </div>
  );
}

const CanvasItem = memo(function CanvasItem({ widget }: { widget: WidgetSpec }) {
  const selected = useDesigner((s) => s.selectedId === widget.id);
  const select = useDesigner((s) => s.select);
  const removeWidget = useDesigner((s) => s.removeWidget);
  const duplicateWidget = useDesigner((s) => s.duplicateWidget);
  const preview = useWidgetPreview(widget);
  const error = preview?.error ?? null;

  return (
    <div
      onMouseDown={() => select(widget.id)}
      className={cn(
        "group relative flex h-full w-full cursor-grab flex-col overflow-hidden rounded-xl border bg-white shadow-xs transition-shadow active:cursor-grabbing",
        selected ? "border-indigo-500 ring-2 ring-indigo-500/25" : "border-zinc-200 hover:border-zinc-300 hover:shadow-sm",
      )}
    >
      <div
        className={cn(
          "absolute top-1.5 right-1.5 z-10 flex items-center gap-0.5 rounded-lg border border-zinc-200 bg-white/95 p-0.5 shadow-sm transition-opacity",
          selected ? "opacity-100" : "opacity-0 group-hover:opacity-100",
        )}
      >
        <span className="flex items-center gap-1 px-1.5 text-[11px] text-zinc-500">
          <GripVertical className="size-3" />
          <WidgetIcon type={widget.type} className="size-3" />
          {typeLabel(widget.type)}
        </span>
        <button
          type="button"
          title="Duplicate"
          className="no-drag rounded-md p-1 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
          onClick={(e) => {
            e.stopPropagation();
            duplicateWidget(widget.id);
          }}
        >
          <Copy className="size-3.5" />
        </button>
        <button
          type="button"
          title="Delete"
          className="no-drag rounded-md p-1 text-zinc-500 hover:bg-red-50 hover:text-red-600"
          onClick={(e) => {
            e.stopPropagation();
            removeWidget(widget.id);
          }}
        >
          <Trash2 className="size-3.5" />
        </button>
      </div>
      {preview?.loading && (
        <div className="absolute top-2 left-2 z-10 flex items-center gap-1 rounded-md bg-white/90 px-1.5 py-0.5 text-[10px] text-zinc-500 shadow-xs">
          <Spinner className="size-3" /> querying
        </div>
      )}
      {widget.type === "text" && widget.options.narrative && (
        <div className="absolute bottom-2 left-2 z-10 flex items-center gap-1 rounded-md bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700">
          <Sparkles className="size-3" /> AI narrative at run time
        </div>
      )}
      <div className="min-h-0 flex-1">
        <WidgetRenderer
          spec={widget}
          data={preview?.data ?? null}
          loading={!!preview?.loading && !preview?.data}
          error={error}
          mode="design"
        />
      </div>
      {error && preview?.data && (
        <div className="flex items-center gap-1 border-t border-red-100 bg-red-50 px-2 py-1 text-[11px] text-red-700">
          <AlertTriangle className="size-3 shrink-0" />
          <span className="truncate">{error}</span>
        </div>
      )}
    </div>
  );
});
