"use client";

import { useEffect, useMemo } from "react";
import { cleanValues } from "@/components/params/presets";
import { archetypeApi, schemaApi, widgetApi } from "@/lib/endpoints";
import { useQuery } from "@/lib/hooks";
import { needsData, useDesigner } from "@/lib/stores/designer";
import type { WidgetSpec } from "@/lib/types";
import { errorMessage } from "@/lib/utils";

export function useArchetypes() {
  return useQuery("archetypes", archetypeApi.list);
}

export function useTables() {
  return useQuery("tables", schemaApi.tables);
}

export function useColumns(table: string | null | undefined) {
  return useQuery(table ? `columns:${table}` : null, () => schemaApi.columns(table!));
}

/** The table a widget actually queries (own source or the format default). */
export function useEffectiveTable(widget?: WidgetSpec | null) {
  const def = useDesigner((s) => s.default_source?.table ?? null);
  return widget?.source?.table || def;
}

const PREVIEW_DEBOUNCE_MS = 500;

/**
 * Live data for one widget on the canvas. Re-fetches (debounced) whenever anything that
 * affects the query changes: source, archetype, filters, runtime params or preview values.
 * Layout, title and presentation options do not trigger a refetch.
 */
export function useWidgetPreview(widget: WidgetSpec) {
  const params = useDesigner((s) => s.params);
  const previewValues = useDesigner((s) => s.previewValues);
  const defaultSource = useDesigner((s) => s.default_source);
  const setPreview = useDesigner((s) => s.setPreview);
  const preview = useDesigner((s) => s.previews[widget.id]);

  const wantsData = needsData(widget.type) && !(widget.type === "text" && widget.options.narrative);
  const values = useMemo(() => cleanValues(previewValues), [previewValues]);

  const key = useMemo(
    () =>
      wantsData
        ? JSON.stringify({
            t: widget.type,
            s: widget.source,
            a: widget.archetype,
            f: widget.filters,
            i: widget.ignore_params,
            p: params,
            v: values,
            d: defaultSource,
          })
        : null,
    [
      wantsData,
      widget.type,
      widget.source,
      widget.archetype,
      widget.filters,
      widget.ignore_params,
      params,
      values,
      defaultSource,
    ],
  );

  useEffect(() => {
    if (!key) return;
    const current = useDesigner.getState().previews[widget.id];
    if (current?.key === key && !current.error && !current.loading) return;
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      const prev = useDesigner.getState().previews[widget.id];
      setPreview(widget.id, { data: prev?.data, loading: true, error: null, key });
      try {
        const spec = useDesigner.getState().widgets.find((w) => w.id === widget.id) ?? widget;
        const data = await widgetApi.preview(
          { widget: spec, params, values, default_source: defaultSource },
          ctrl.signal,
        );
        setPreview(widget.id, { data, loading: false, error: data.error ?? null, key });
      } catch (e) {
        if (ctrl.signal.aborted) return;
        setPreview(widget.id, { data: prev?.data, loading: false, error: errorMessage(e), key });
      }
    }, PREVIEW_DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
    // `widget` itself is read fresh from the store inside the timer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, widget.id, setPreview]);

  return wantsData ? preview : undefined;
}
