"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, Check, CircleDot, Lock, Play, Save, UserRound } from "lucide-react";
import { toast } from "sonner";
import { useColumnValues } from "@/components/params/ParamValueInput";
import { Button } from "@/components/ui/Button";
import { Combobox } from "@/components/ui/Combobox";
import { PageSpinner } from "@/components/ui/Spinner";
import { connectionApi, formatApi } from "@/lib/endpoints";
import { useQuery } from "@/lib/hooks";
import { useDesigner } from "@/lib/stores/designer";
import { useSession } from "@/lib/stores/session";
import { errorMessage } from "@/lib/utils";
import { AgentBox } from "./AgentBox";
import { Canvas } from "./Canvas";
import { Inspector } from "./Inspector";
import { Palette } from "./Palette";
import { ParamBar } from "./ParamBar";

export function DesignerApp({ formatId }: { formatId: string }) {
  const me = useSession((s) => s.me);
  if (me && me.role !== "designer") {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 py-24 text-center">
        <Lock className="size-8 text-zinc-300" />
        <div className="font-medium text-zinc-900">Only designers can edit report formats</div>
        <p className="text-sm text-zinc-500">You can still generate reports from saved formats.</p>
        <Link href="/generate" className="text-sm font-medium text-indigo-600">
          Go to Generate →
        </Link>
      </div>
    );
  }
  return <DesignerLoader formatId={formatId} />;
}

function DesignerLoader({ formatId }: { formatId: string }) {
  const loaded = useDesigner((s) => s.loaded);
  const init = useDesigner((s) => s.init);
  const reset = useDesigner((s) => s.reset);
  const connection = useQuery("connection", connectionApi.get);
  const connReady = !connection.loading;
  const defaultTable = connection.data?.default_table ?? null;
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const s = useDesigner.getState();
    if (s.handoffId && s.handoffId === formatId) {
      // We just created this format and the URL changed from /designer/new; keep the state.
      useDesigner.setState({ handoffId: null });
      return;
    }
    if (!connReady) return;
    let cancelled = false;
    if (formatId === "new") {
      init(null, { defaultTable });
    } else {
      formatApi.get(formatId).then(
        (f) => !cancelled && init(f, { defaultTable }),
        (e) => !cancelled && setError(errorMessage(e)),
      );
    }
    return () => {
      cancelled = true;
    };
  }, [formatId, connReady, defaultTable, init]);

  useEffect(
    () => () => {
      if (!useDesigner.getState().handoffId) reset();
    },
    [reset],
  );

  if (error) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 py-24 text-center">
        <div className="font-medium text-zinc-900">Could not open this report format</div>
        <p className="text-sm text-red-600">{error}</p>
        <Link href="/dashboard" className="text-sm font-medium text-indigo-600">
          Back to dashboard
        </Link>
      </div>
    );
  }
  if (!loaded) return <PageSpinner label="Opening designer…" />;
  return <Designer connected={!!connection.data?.connected} />;
}

function Designer({ connected }: { connected: boolean }) {
  const router = useRouter();
  const dirty = useDesigner((s) => s.dirty);
  const formatId = useDesigner((s) => s.formatId);
  const version = useDesigner((s) => s.version);
  const [saving, setSaving] = useState(false);

  const save = useCallback(async (): Promise<string | null> => {
    const s = useDesigner.getState();
    setSaving(true);
    try {
      const body = s.toBody();
      const f = s.formatId ? await formatApi.update(s.formatId, body) : await formatApi.create(body);
      s.markSaved(f, { handoff: !s.formatId });
      if (!s.formatId) router.replace(`/designer/${f.id}`);
      toast.success(`Saved “${f.name}”`, { description: `Version ${f.version}` });
      return f.id;
    } catch (e) {
      toast.error("Could not save", { description: errorMessage(e) });
      return null;
    } finally {
      setSaving(false);
    }
  }, [router]);

  const generate = async () => {
    let id = useDesigner.getState().formatId;
    if (!id || useDesigner.getState().dirty) id = await save();
    if (id) router.push(`/generate?format=${id}`);
  };

  // Ctrl/Cmd+S saves.
  const saveRef = useRef(save);
  useEffect(() => {
    saveRef.current = save;
  });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void saveRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Warn about unsaved changes on reload/close and on in-app link navigation.
  useEffect(() => {
    if (!dirty) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    const onClick = (e: MouseEvent) => {
      const a = (e.target as HTMLElement).closest?.("a[href]") as HTMLAnchorElement | null;
      if (!a || a.target === "_blank" || a.hasAttribute("download")) return;
      const url = new URL(a.href, window.location.href);
      if (url.origin !== window.location.origin || url.pathname === window.location.pathname) return;
      if (!window.confirm("You have unsaved changes to this report format. Leave without saving?")) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    document.addEventListener("click", onClick, true);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      document.removeEventListener("click", onClick, true);
    };
  }, [dirty]);

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col overflow-hidden">
      <div className="flex items-center gap-4 border-b border-zinc-200 bg-white px-4 py-2">
        <Link href="/dashboard" className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-100" title="Back to dashboard">
          <ArrowLeft className="size-4" />
        </Link>
        <FormatMeta />
        <AgentBox />
        <div className="flex shrink-0 items-center gap-2">
          <span className="hidden items-center gap-1 text-xs text-zinc-500 lg:flex">
            {dirty ? (
              <>
                <CircleDot className="size-3 text-amber-500" /> Unsaved
              </>
            ) : formatId ? (
              <>
                <Check className="size-3 text-emerald-500" /> Saved · v{version}
              </>
            ) : (
              "Not saved yet"
            )}
          </span>
          <Button variant="outline" onClick={() => void save()} loading={saving}>
            <Save className="size-4" /> Save
          </Button>
          <Button onClick={generate} disabled={saving}>
            <Play className="size-4" /> Generate…
          </Button>
        </div>
      </div>
      <ParamBar />
      {!connected && (
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
          Snowflake is not connected, so widgets cannot load data.{" "}
          <Link href="/settings/connection" className="font-medium underline">
            Connect now
          </Link>
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        <Palette />
        <div className="min-w-0 flex-1 overflow-y-auto bg-zinc-100/60">
          <Canvas />
        </div>
        <Inspector />
      </div>
    </div>
  );
}

function FormatMeta() {
  const name = useDesigner((s) => s.name);
  const description = useDesigner((s) => s.description);
  const clientScope = useDesigner((s) => s.client_scope);
  const setMeta = useDesigner((s) => s.setMeta);
  const table = useDesigner((s) => s.default_source?.table ?? null);
  const clientColumn = useDesigner((s) => s.params.find((p) => p.type === "client")?.column ?? "CLIENT_NAME");
  const clients = useColumnValues(table, clientColumn);

  return (
    <div className="flex min-w-0 shrink-0 items-center gap-3">
      <div className="flex w-64 min-w-0 flex-col">
        <input
          value={name}
          onChange={(e) => setMeta({ name: e.target.value })}
          placeholder="Report name"
          className="truncate rounded px-1 text-sm font-semibold text-zinc-900 outline-none hover:bg-zinc-50 focus:bg-zinc-50 focus:ring-1 focus:ring-indigo-300"
        />
        <input
          value={description}
          onChange={(e) => setMeta({ description: e.target.value })}
          placeholder="Add a description…"
          className="truncate rounded px-1 text-xs text-zinc-500 outline-none hover:bg-zinc-50 focus:bg-zinc-50 focus:ring-1 focus:ring-indigo-300"
        />
      </div>
      <div className="hidden w-52 items-center gap-1.5 xl:flex" title="Tailored for client (optional)">
        <UserRound className="size-4 shrink-0 text-zinc-400" />
        <Combobox
          size="sm"
          value={clientScope}
          onChange={(v) => setMeta({ client_scope: v })}
          options={clients.options}
          loading={clients.loading}
          placeholder="Tailored for client…"
        />
      </div>
    </div>
  );
}
