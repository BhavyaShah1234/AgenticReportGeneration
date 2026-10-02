"use client";

import { useEffect, useState } from "react";
import { ArrowUp, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Spinner } from "@/components/ui/Spinner";
import { Tabs } from "@/components/ui/Tabs";
import { agentApi } from "@/lib/endpoints";
import { normalizeWidget, useDesigner } from "@/lib/stores/designer";
import type { ReportFormatBody } from "@/lib/types";
import { cn, errorMessage } from "@/lib/utils";

type Mode = "widget" | "report";

const PLACEHOLDERS: Record<Mode, string> = {
  widget: "e.g. monthly revenue for Classic Cars as a line chart",
  report: "e.g. a quarterly business review for one client",
};

/** Natural-language "Ask the agent" box: add one widget, or draft a whole report. */
export function AgentBox() {
  const [mode, setMode] = useState<Mode>("widget");
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [draft, setDraft] = useState<{ format: ReportFormatBody; explanation: string } | null>(null);

  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    const t = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(t);
  }, [busy]);

  const ask = async () => {
    const text = prompt.trim();
    if (!text || busy) return;
    const s = useDesigner.getState();
    setBusy(true);
    setElapsed(0);
    try {
      if (mode === "widget") {
        const res = await agentApi.widget({
          prompt: text,
          table: s.default_source?.table ?? null,
          params: s.params,
          existing_widgets: s.widgets,
        });
        s.addWidget(normalizeWidget(res.widget), { atBottom: true });
        toast.success("Widget added", { description: res.explanation || undefined });
        setPrompt("");
      } else {
        const res = await agentApi.report({ prompt: text, table: s.default_source?.table ?? null });
        if (s.widgets.length === 0) {
          s.replaceWithDraft(res.format);
          toast.success(`Drafted “${res.format.name}”`, { description: res.explanation || undefined });
          setPrompt("");
        } else {
          setDraft(res);
        }
      }
    } catch (e) {
      toast.error("The agent could not complete that", { description: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  const applyDraft = (how: "replace" | "merge") => {
    if (!draft) return;
    const s = useDesigner.getState();
    if (how === "replace") s.replaceWithDraft(draft.format);
    else s.mergeDraft(draft.format);
    toast.success(how === "replace" ? `Replaced with “${draft.format.name}”` : "Draft widgets appended");
    setDraft(null);
    setPrompt("");
  };

  return (
    <div className="flex min-w-0 flex-1 items-center gap-2">
      <Tabs
        size="sm"
        value={mode}
        onChange={setMode}
        items={[
          { value: "widget", label: "Add widget" },
          { value: "report", label: "Draft report" },
        ]}
      />
      <div
        className={cn(
          "flex h-9 min-w-0 flex-1 items-center gap-2 rounded-lg border bg-white pr-1 pl-3 shadow-xs transition-colors",
          busy ? "border-indigo-300 bg-indigo-50/40" : "border-zinc-200 focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20",
        )}
      >
        <Sparkles className="size-4 shrink-0 text-indigo-500" />
        {busy ? (
          <span className="flex flex-1 items-center gap-2 truncate text-sm text-indigo-700">
            <Spinner className="size-3.5" />
            {mode === "widget" ? "Designing a widget" : "Drafting a report"}… {elapsed}s
            <span className="hidden text-xs text-indigo-400 lg:inline">(local LLM, can take up to a minute)</span>
          </span>
        ) : (
          <input
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void ask();
            }}
            placeholder={`Ask the agent: ${PLACEHOLDERS[mode]}`}
            className="h-full min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-zinc-400"
          />
        )}
        <Button size="icon-sm" onClick={ask} disabled={!prompt.trim() || busy} title="Ask">
          <ArrowUp className="size-4" />
        </Button>
      </div>

      <Dialog
        open={!!draft}
        onClose={() => setDraft(null)}
        title={`Apply draft “${draft?.format.name ?? ""}”?`}
        description="Your canvas already has widgets. Replace them, or append the draft below them."
        footer={
          <>
            <Button variant="outline" onClick={() => setDraft(null)}>
              Cancel
            </Button>
            <Button variant="outline" onClick={() => applyDraft("merge")}>
              Merge (append)
            </Button>
            <Button variant="danger" onClick={() => applyDraft("replace")}>
              Replace canvas
            </Button>
          </>
        }
      >
        {draft && (
          <div className="flex flex-col gap-3 text-sm">
            {draft.explanation && <p className="text-zinc-600">{draft.explanation}</p>}
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
              <div className="text-xs font-medium text-zinc-500">
                {draft.format.widgets.length} widgets · {draft.format.params.length} parameters
              </div>
              <ul className="mt-1 list-disc pl-5 text-zinc-700">
                {draft.format.widgets.slice(0, 10).map((w, i) => (
                  <li key={w.id || i}>
                    {w.title || w.options?.text || w.type} <span className="text-xs text-zinc-400">({w.type})</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}
